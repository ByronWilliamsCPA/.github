# Handoff: Issue #168, merge_group security-gate coverage gap

> **Status**: Resolved by PR #178 (Option 1 selected)
> **Date prepared**: 2026-05-26
> **Audience**: Incoming team picking up the merge_queue rollout (parent issue #154)
> **Estimated effort**: 1 hr (Option 1), half-day (Option 2), zero now / unbounded later (Option 3)
> **Time sensitivity**: Should land **before** `merge_queue` is enabled on the first consumer repo. Today the gate passes a queued PR with 4 of 5 security sub-scans, which is exploitable.

---

## 1. One-paragraph context

PR #163 (merged 2026-05-25) added the `merge_group:` trigger to nine workflow templates so consumer repos can enable GitHub merge queue. The `python-security-analysis.yml` template runs five security sub-scans (CodeQL, Dependency Review, Bandit, OSV-Scanner, OWASP Dependency-Check) behind an aggregator job (`security-gate`). The Dependency Review sub-scan uses `actions/dependency-review-action`, which does **not** support `merge_group` events because it needs PR base/head SHAs that only exist in `pull_request` context. That sub-scan is therefore explicitly gated to `pull_request` only and is silently skipped on `merge_group` runs. The aggregator's `is_acceptable()` helper treats `skipped` as success, so a queued PR currently passes the security gate without dependency-vulnerability coverage ever running.

---

## 2. Why this matters now

The workflow templates already ship the `merge_group:` trigger; they are inert until a consumer repo flips `merge_queue` on in its branch ruleset. The moment that flip happens, the coverage gap goes live. Issue #154 is the rollout plan for that flip; **#168 should land before #154's per-repo rollout starts**. Failure mode: a Renovate dependency PR with a newly-introduced CVE could be batched into the queue, pass the gate on `merge_group` (because dependency review is skipped), and land on `main`.

The other four sub-scans (CodeQL, Bandit, OSV-Scanner, OWASP Dependency-Check) all run on `merge_group`, so coverage is 4-of-5 today. The work is to restore 5-of-5.

---

## 3. Current state, with line references

**File**: [`workflow-templates/python-security-analysis.yml`](../../workflow-templates/python-security-analysis.yml)

> Line numbers below reference the **pre-PR-178** state of the file (the state this section documented before the comment expansion shipped). After PR #178 the cited lines shift to: 30-47 (DESIGN DECISION block, formerly KNOWN LIMITATION), 146-152 (dependency-security `if:`), 227-231 (osv-scanner job, now preceded by a role-marker comment added in PR #178), and 404-439 (security-gate aggregator). Use search-by-keyword in the current file to navigate.

The known-limitation comment is documented in the trigger block:

```yaml
# workflow-templates/python-security-analysis.yml:30-45
# CRITICAL: merge_group fires against the queue's speculative merge commit.
# Security gate must run on the queue ref so vulnerabilities introduced by
# the speculative merge are caught before landing on main. See CI-040.
#
# KNOWN LIMITATION: actions/dependency-review-action does not support
# merge_group events ... Follow-up: track dedicated dependency-CVE check
# on merge_group as a coverage gap (issue #168).
merge_group:
```

The actual gate that excludes the job from `merge_group`:

```yaml
# workflow-templates/python-security-analysis.yml:142-149
  dependency-security:
    name: Dependency Security Review
    runs-on: ubuntu-latest
    needs: detect-changes
    if: |
      github.event_name == 'pull_request' &&
      needs.detect-changes.outputs.security_files == 'true'
```

The aggregator that silently passes when the job is skipped:

```yaml
# workflow-templates/python-security-analysis.yml:398-433
  security-gate:
    needs:
      - detect-changes
      - codeql-analysis
      - dependency-security    # <-- this is the one that gets skipped
      - security-scanning
      - osv-scanner
      - owasp-dependency-check
    if: always()
    steps:
      - run: |
          is_acceptable() {
            [[ "$1" == "success" || "$1" == "skipped" ]]
          }
          # if every sub-scan is "success or skipped", gate passes
```

The existing OSV-Scanner job, which is the candidate to repurpose for Option 1:

```yaml
# workflow-templates/python-security-analysis.yml:220-225
  osv-scanner:
    name: OSV Vulnerability Scanner
    runs-on: ubuntu-latest
    needs: detect-changes
    if: needs.detect-changes.outputs.security_files == 'true'  # no event_name filter
```

Note: `osv-scanner` already has **no `event_name` filter**, so it fires on `merge_group` by default if `detect-changes` produces an output. That is the architectural pivot point that makes Option 1 cheap.

---

## 4. Three options, with concrete trade-offs

### Option 1 (recommended): Document OSV-Scanner as the merge_group dependency-CVE check

**What changes**: zero code. Update the `# KNOWN LIMITATION` block at lines 30-45 to state that OSV-Scanner is the canonical dependency-CVE check for `merge_group` refs, and dependency-review is the PR-context-only complement. Update the issue and the `CRITICAL` comment to reflect the new state.

**Pros**:
- Smallest diff possible (comment-only).
- OSV-Scanner already runs on `merge_group` and already feeds the gate via `needs:`. The 5-of-5 coverage assertion was wrong in the first place; the actual coverage is already CodeQL + Bandit + OSV-Scanner + OWASP = 4 dep/SAST sub-scans, and the *only* missing one is dependency-review, which overlaps with OSV-Scanner functionally.
- No new CI minute cost.

**Cons**:
- Loses the GPL-2.0/GPL-3.0 license deny-list that `dependency-review-action` provides (see lines 168 of the template). If license enforcement on merge_group is a hard requirement, this option does not satisfy it.
- Loses the PR comment summary that dependency-review posts; minor since SonarCloud + Copilot already surface PR-level findings.

**Verification this is safe**:
- Run `gh api repos/<org>/<repo>/commits/<merge_group_sha>/check-runs --jq '.check_runs[] | select(.name | contains("OSV"))'` against a sacrificial queue ref to confirm OSV-Scanner emits.
- Compare an OSV-Scanner finding set against a dependency-review finding set on the same PR; if OSV catches everything dep-review does (ignoring license findings), the architectural claim holds.

### Option 2: Add a dedicated merge_group dependency check

**What changes**: new job in `python-security-analysis.yml`, gated to `merge_group` only, runs `osv-scanner` (or `pip-audit`) scoped to the dependency files (`pyproject.toml`, `poetry.lock`, `uv.lock`). Added to `security-gate`'s `needs:` so the aggregator can fail.

**Pros**:
- Clearer signal in CI; the check name explicitly indicates it ran on a queued PR.
- License enforcement can be preserved by adding `osv-scanner --license-check` or an equivalent.
- Surfaces dependency-CVE coverage gaps explicitly, not buried in a comment.

**Cons**:
- Doubles dependency scanning on `pull_request` events (osv-scanner runs twice) unless gated carefully.
- More moving parts to maintain across the 9 templates.
- CI minute cost: extra job per queued PR.

### Option 3: Wait for `actions/dependency-review-action` to add `merge_group` support

**What changes**: nothing now; track the upstream issue in `actions/dependency-review-action`.

**Pros**:
- Zero work today.

**Cons**:
- Indefinite gap. The upstream issue has been open since at least 2024 without resolution.
- Blocks #154's rollout indefinitely, or accepts the security gap during rollout.

---

## 5. Recommended path

**Option 1**, contingent on the license-check question. The receiving team should answer this **before** starting:

> Is GPL-2.0/GPL-3.0 license enforcement on `merge_group` runs a hard requirement, or can it stay PR-only?

- If PR-only is acceptable: Option 1 is correct. Ship the comment update, close #168.
- If `merge_group` license enforcement is required: Option 2 is correct, with `osv-scanner --license-check` added to the new job.

This decision can be made in 5 minutes by checking the standards manifest (CI-040 and related entries) and any compliance docs that touch license policy. The most likely answer is "PR-only is fine," because license findings are not exploitable code paths, they are policy violations that can be caught at PR time and don't change between PR head and queue head.

---

## 6. Implementation plan for Option 1

1. Create worktree per repo convention: `git worktree add .worktrees/issue-168-merge-group-osv -b claude/issue-168-merge-group-osv origin/main`.
2. Edit [`workflow-templates/python-security-analysis.yml`](../../workflow-templates/python-security-analysis.yml) lines 30-45:
   - Replace the "Follow-up: track dedicated dependency-CVE check ..." sentence with one that states OSV-Scanner is the canonical merge_group dependency check.
   - Make the dep-review-is-PR-only behavior an explicit design decision, not a known limitation.
3. (Optional, not implemented in PR #178) Add an `if: github.event_name == 'merge_group'` echo step to `osv-scanner` job that prints "Running as the merge_group dependency-CVE check" so operators see the role in logs. PR #178 used a YAML role-marker comment above the job (lines 223-226 post-PR) in place of a run-time echo; the role is visible in the file rather than in run logs. If runtime visibility becomes important, open a follow-up issue to add the echo step.
4. Run `pre-commit run --files workflow-templates/python-security-analysis.yml` (must pass: yamllint, no-em-dash, secrets scans, commitizen).
5. Sign and push: `git commit -S` with conventional commit `docs(security-analysis): document OSV-Scanner as merge_group dependency-CVE check (#168)`.
6. Open PR against `main`. Reference #168 and #154 in the body.
7. After merge, comment on #154 noting that the security-gate coverage gap is documented as closed, and the merge_queue per-repo rollout is unblocked.

## 7. Implementation plan for Option 2 (if license enforcement required)

1. Same worktree setup.
2. Add a new job `dependency-security-mq` to `workflow-templates/python-security-analysis.yml`, gated `if: github.event_name == 'merge_group' && needs.detect-changes.outputs.security_files == 'true'`. Run `osv-scanner` with `--license-check`, scoped to lockfile paths.
3. Add `dependency-security-mq` to `security-gate`'s `needs:` list.
4. Update the `# KNOWN LIMITATION` block to reflect the new state.
5. Pre-commit, sign, push, PR. Same conventional commit format.
6. **Verification step that Option 1 doesn't need**: enable `merge_queue` on a sacrificial repo (suggest `ByronWilliamsCPA/llc-manager` or a fresh test repo), push a PR with a known-vulnerable dependency, confirm the gate fails on the queue ref. Capture the `gh api .../check-runs` output in the PR body.

---

## 8. Verification path (both options)

```bash
# Pick a sacrificial repo
REPO=ByronWilliamsCPA/llc-manager

# Find a recent merge_group SHA on that repo
gh api "repos/$REPO/actions/runs?event=merge_group&per_page=1" --jq '.workflow_runs[0].head_sha'

# Confirm the dependency-CVE check is present on that ref
gh api "repos/$REPO/commits/<sha>/check-runs" \
  --jq '.check_runs[] | select(.name | test("OSV|Dependency")) | {name, conclusion}'

# Expected after Option 1:
#   {"name": "Security Analysis / OSV Vulnerability Scanner", "conclusion": "success"}
# Expected after Option 2:
#   {"name": "Security Analysis / Dependency Security (merge_group)", "conclusion": "success"}
```

If the receiving team needs an end-to-end test (a queued PR with a real CVE), the cleanest path is to point at a pinned vulnerable version of a small dep like `urllib3==1.26.5` (CVE-2023-43804) in a test branch.

---

## 9. Dependencies, blockers, risks

- **Not blocked by anything**; PR #163 already landed the trigger.
- **Blocks #154** (merge_queue per-repo rollout), or at minimum should land first so rollout doesn't open a known security gap.
- **Risk if shipped wrong**: Option 1 over-relies on OSV-Scanner. If OSV-Scanner has a future outage or false-negative class, dependency coverage on merge_group degrades silently. Mitigation: the standards manifest should record OSV-Scanner as the canonical merge_group dep check, and add a self-test that fails if osv-scanner is removed or its `needs:` link is broken.

---

## 10. References

- **Parent**: [#154 Enable GitHub merge_queue for repos with auto-merging dep bumps](https://github.com/ByronWilliamsCPA/.github/issues/154)
- **This issue**: [#168 Add osv-scanner dependency check on merge_group events](https://github.com/ByronWilliamsCPA/.github/issues/168)
- **Trigger rollout PR**: [#163 feat(workflow-templates): add merge_group trigger for GitHub merge queue](https://github.com/ByronWilliamsCPA/.github/pull/163)
- **Standards manifest**: `CI-040` (merge_group required)
- **Target file**: [`workflow-templates/python-security-analysis.yml`](../../workflow-templates/python-security-analysis.yml)
- **Reusable workflow consumed by repos**: [`.github/workflows/python-security-analysis.yml`](../../.github/workflows/python-security-analysis.yml). **Do not forget to apply the same change to this file** if Option 2 is chosen; the template and the reusable have diverged in the past (#139 documented this self-test gap).
- **Repo branch convention**: `claude/<description>-<id>`, see [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md).
- **No em-dashes** in code, comments, commits, or PR descriptions; the `no-em-dash` pre-commit hook (PC-011) enforces this.

---

## 11. Quick-start (Option 1, 5 lines of shell)

```bash
git worktree add .worktrees/issue-168-merge-group-osv -b claude/issue-168-merge-group-osv origin/main
cd .worktrees/issue-168-merge-group-osv
# edit workflow-templates/python-security-analysis.yml lines 30-45 per Section 6 above
pre-commit run --files workflow-templates/python-security-analysis.yml
git add workflow-templates/python-security-analysis.yml && git commit -S -m "docs(security-analysis): document OSV-Scanner as merge_group dependency-CVE check (#168)"
git push -u origin claude/issue-168-merge-group-osv && gh pr create --base main --fill
```

## 12. Open question for receiving team (resolved in PR #178)

> Is GPL-2.0/GPL-3.0 license enforcement on `merge_group` runs a hard requirement, or is it acceptable to leave license-policy checks at PR time only?

Answer determined Option 1 vs Option 2. The receiving team resolved this in PR #178.

### Resolution

PR-only is acceptable. `python-sbom.yml`'s `license-compliance` job is `fail-on-forbidden-licenses: false` (warn-only) and only runs on `push:main`, `release`, and the weekly schedule. `dependency-review-action`'s `deny-licenses: GPL-2.0, GPL-3.0` is therefore the only fail-on license policy in the repo, and it lives at PR review time. The queued PR's deps were already enforced at that gate; replicating the check on the speculative merge ref adds no security signal because license findings are PR-review policy, not exploitable speculative-merge regressions. Option 1 selected; resolved in PR #178.
