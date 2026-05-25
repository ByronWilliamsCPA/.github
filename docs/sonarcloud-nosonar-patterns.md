# SonarCloud NOSONAR Behavior in GitHub Actions YAML

**Date:** 2026-05-25
**Author:** Claude Code (empirical observations from PR #157 remediation)
**Scope:** Empirical findings on which NOSONAR placement patterns are honored by SonarCloud's `githubactions` rule set, derived from a live remediation attempt that flagged the limits of preceding-line suppression. Targeted at teams maintaining reusable GitHub Actions workflows where rules like `githubactions:S8541` (`--no-build`) and `githubactions:S8544` (`--frozen`) require deliberate suppression with rationale.

---

## TL;DR

Two NOSONAR placement patterns appear in our reusable workflows. Their effectiveness is NOT equivalent. Use this table when adding new suppressions.

| Placement | Example | S8541 honored? | S8544 honored? | Notes |
|---|---|---|---|---|
| Inline on YAML `run:` line | `run: uv sync --all-extras $NO_BUILD_FLAG  # NOSONAR(S8541,S8544): ...` | Yes | Yes | Used at [`python-compatibility.yml:302`](../.github/workflows/python-compatibility.yml#L302); proven on main. Comma-separated rule list accepted. |
| Preceding-line bash `#` comment inside `\|` block scalar, **with literal `--frozen` on the next line** | `# NOSONAR(S8541): ...\n  uv run --frozen $NO_BUILD_FLAG ...` | Yes | N/A (no S8544 fires when literal --frozen present) | Used at [`python-compatibility.yml:336-337`](../.github/workflows/python-compatibility.yml#L336-L337); proven on main. |
| Preceding-line bash `#` comment inside `\|` block scalar, **with dynamic `$FROZEN_FLAG`** | `# NOSONAR(S8541,S8544): ...\n  uv run $FROZEN_FLAG $NO_BUILD_FLAG ...` | Not tested in isolation | **NOT honored** | Attempted at [`python-fips-compatibility.yml:209-210` and `:219-220`](../.github/workflows/python-fips-compatibility.yml#L209) in PR #157 commit `e797676`. SonarCloud continued to flag both S8541 and S8544 on the `uv run` lines after the suppression landed. |

**Rule of thumb**: Inline-on-YAML-line suppression works for any rule combination. Preceding-line suppression appears to work only when the offending line has the literal token visible (so SonarCloud's pattern matcher already sees the safe code and the NOSONAR is just dressing for the orthogonal rule). When the line itself triggers the rule (dynamic flag), preceding-line NOSONAR is unreliable; restructure the code so the literal is visible.

---

## Background

SonarCloud's `githubactions` rules pattern-match against the literal text of YAML `run:` block scalars. They look for command tokens like `--frozen` and `--no-build`. When those tokens are injected via environment variables (e.g., `$FROZEN_FLAG: ${{ ... && '--frozen' || '' }}`), the scanner cannot follow the indirection and fires the rule even when the runtime command is safe.

Two workflows in this repo both detect repo state at job start and then run `uv sync` / `uv run`:

1. **`python-compatibility.yml`** (already on main, Quality Gate: PASSING, zero open vulnerabilities)
2. **`python-fips-compatibility.yml`** (PR #157 head before re-fix: 6 open MAJOR vulnerabilities; after partial fix: 4 open)

Both attempted to suppress S8541/S8544 with NOSONAR comments. The first succeeds; the second is partly succeeding. The asymmetry is the evidence base for this doc.

---

## Empirical observations from PR #157

Starting commit `04cdd90` introduced this pattern in both `fips-check` and `fips-runtime-test` jobs:

```yaml
- name: ...
  env:
    FROZEN_FLAG: ${{ steps.detect.outputs.state == 'uv-locked' && '--frozen' || '' }}
  run: uv sync --all-extras $FROZEN_FLAG $NO_BUILD_FLAG  # NOSONAR S8541
```

SonarCloud reported 6 open MAJOR vulnerabilities at three locations:

- `fips-check` job lines 201, 210 (two `uv run $FROZEN_FLAG` invocations in a `\|` block)
- `fips-runtime-test` job line 440 (the `uv sync` line shown above) and line 449 (a `uv run $FROZEN_FLAG` in another `\|` block)

Commit `e797676` (this PR fix pass 1) applied two changes:

1. **`fips-runtime-test` job** (mirrors `python-compatibility.yml` pattern):
   - Split `Install dependencies` into two steps: one for `uv-locked` (literal `--frozen`, no suppression), one for `uv-no-lock` (no `--frozen`, `# NOSONAR(S8541,S8544)` inline on the YAML `run:` line).
   - `Test crypto imports` step: dropped `FROZEN_FLAG` env, used literal `uv run --frozen $NO_BUILD_FLAG`, added `# NOSONAR(S8541)` as a preceding bash comment inside the `\|` block.
2. **`fips-check` job** (kept dynamic `$FROZEN_FLAG` because no install step pre-generates `uv.lock`):
   - Added `# NOSONAR(S8541,S8544): ...` as a preceding bash comment inside the `\|` block, on the line before each of the two `uv run $FROZEN_FLAG` invocations.

After commit `e797676` landed and SonarCloud re-analyzed:

- The `fips-runtime-test` changes worked. Lines 440 and 449 are no longer flagged.
- The `fips-check` changes did NOT work. Lines 210 and 220 still report both S8541 and S8544.

The literal text of the four remaining open issues:

```text
{rule: githubactions:S8541, severity: MAJOR, line: 210}
{rule: githubactions:S8544, severity: MAJOR, line: 210}
{rule: githubactions:S8541, severity: MAJOR, line: 220}
{rule: githubactions:S8544, severity: MAJOR, line: 220}
```

---

## Hypothesis

Two possibilities, neither yet confirmed by SonarCloud documentation:

1. **Preceding-line NOSONAR is not honored at all by the `githubactions` rule set, but it works for S8541 in particular cases** because the line below ALSO satisfies the rule on its own (literal `--frozen` is visible, so S8544 never fires regardless of the comment, and S8541 happens to also be tolerated because the line is otherwise clean). In other words, the apparent "success" of preceding-line NOSONAR on `python-compatibility.yml:336-337` is a coincidence of the line itself being inherently safer.

2. **The comma-separated rule-list syntax `NOSONAR(S8541,S8544)` is parsed differently in preceding-line position than in inline position.** SonarCloud's general NOSONAR docs accept comma lists, but the YAML/githubactions scanner may parse the comment differently when it occurs inside a block scalar.

Either way, the practical implication is the same: **do not rely on preceding-line NOSONAR to suppress S8544 when the line itself contains a dynamic flag.**

---

## Recommended patterns

**Pattern A (preferred): use inline NOSONAR on the YAML `run:` line**

```yaml
- name: Install dependencies (uv without lockfile)
  if: steps.detect.outputs.state == 'uv-no-lock'
  run: uv sync --all-extras $NO_BUILD_FLAG  # NOSONAR(S8541,S8544): --no-build opt-out via `no-build` input; no uv.lock by design on this path
```

This places the NOSONAR on the same physical YAML line as the offending command. SonarCloud's parser handles it predictably and accepts comma-separated rule lists. Use this when the entire command fits on one line.

**Pattern B (acceptable for multi-line commands): make the literal visible, then suppress only S8541 with a preceding-line comment**

```yaml
run: |
  # NOSONAR(S8541): --no-build is opt-out via `no-build` workflow input
  uv run --frozen $NO_BUILD_FLAG python "$SCRIPT_PATH" \
    --arg-a \
    --arg-b
```

Requires that an install step run before this block so `uv.lock` exists and `--frozen` is structurally safe. The literal `--frozen` in the command prevents S8544 from firing; the preceding-line `# NOSONAR(S8541)` covers `--no-build` (which is dynamic via `$NO_BUILD_FLAG`).

**Anti-pattern (avoid): preceding-line NOSONAR with both flags dynamic**

```yaml
run: |
  # NOSONAR(S8541,S8544): --no-build via input; --frozen via FROZEN_FLAG
  uv run $FROZEN_FLAG $NO_BUILD_FLAG python "$SCRIPT_PATH" \
    --arg-a
```

This is what PR #157 commit `e797676` tried. SonarCloud continues to flag both rules. Either restructure to expose a literal `--frozen` (Pattern B) or rewrite the multi-line command as a single line and use Pattern A.

---

## Restructuring to expose a literal `--frozen`

The most reliable way to suppress S8544 is to remove the dynamic flag entirely. Two structural options:

**Option 1: add install step before run step.** The install step handles the locked/no-lock branching; the run step assumes `uv.lock` exists and uses literal `--frozen`. This is the approach `python-compatibility.yml` uses. Cost: ~1-2 minutes of install runtime per CI job that previously skipped it.

**Option 2: collapse to single-line run command + inline NOSONAR.** Rewrite `uv run $FROZEN_FLAG $NO_BUILD_FLAG python "$SCRIPT_PATH" \\ $A \\ $B` as a single YAML line, then add `# NOSONAR(S8541,S8544): ...` at the end of that line. Cost: line-length warnings from yamllint if the command is long; reduced readability.

For PR #157, Option 1 was selected to mirror the sibling pattern exactly.

---

## Verification protocol

When adding or changing a SonarCloud suppression on a workflow file:

1. Push the change to a feature branch.
2. Wait for the SonarCloud Code Analysis check to complete (typically 2-5 minutes).
3. Query the PR's vulnerabilities via the public API:

   ```bash
   curl -s "https://sonarcloud.io/api/issues/search?componentKeys={PROJECT_KEY}&pullRequest={PR_NUMBER}&types=VULNERABILITY&ps=20&statuses=OPEN,CONFIRMED" \
     | jq '.issues[] | {rule, line, message}'
   ```

4. Check the quality gate:

   ```bash
   curl -s "https://sonarcloud.io/api/qualitygates/project_status?projectKey={PROJECT_KEY}&pullRequest={PR_NUMBER}" \
     | jq '.projectStatus.status'
   ```

Both calls work without authentication for public projects. The pre-commit hook stack and `actionlint` do not catch SonarCloud rule violations; only the remote analysis does. Plan for at least one push-then-wait cycle when changing suppressions.

---

## Cross-references

- Sibling workflow with proven suppression patterns: [`python-compatibility.yml`](../.github/workflows/python-compatibility.yml)
- PR that introduced the failing pattern: [#157](https://github.com/ByronWilliamsCPA/.github/pull/157)
- Related historical fix (sibling SonarCloud remediation): commit `eecbaa3b281b1a39df59466b199d1fb31f638f7f` on branch `chore/python-compatibility-detect-poetry-uv`
- Original `--no-build` input feature: [PR #112](https://github.com/ByronWilliamsCPA/.github/pull/112)
