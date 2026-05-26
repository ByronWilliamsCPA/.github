# SonarCloud NOSONAR Behavior in GitHub Actions YAML

**Date:** 2026-05-25 (initial); strengthened 2026-05-26 with Wave 1C findings from PR #166
**Author:** Claude Code (empirical observations from PR #157 remediation, strengthened by PR #166)
**Scope:** Empirical findings on which NOSONAR placement patterns are honored by SonarCloud's `githubactions` rule set, derived from live remediation attempts that flagged the limits of suppression inside `run: |` block scalars. Targeted at teams maintaining reusable GitHub Actions workflows where rules like `githubactions:S8541` (`--no-build`) and `githubactions:S8544` (`--frozen`) require deliberate suppression with rationale.

---

## TL;DR

Four NOSONAR placement patterns have been empirically tested in our reusable workflows. Their effectiveness is NOT equivalent. Use this table when adding new suppressions.

| Placement | Example | S8541 honored? | S8544 honored? | Notes |
|---|---|---|---|---|
| **Inline on single-line YAML `run:`** | `run: uv sync --all-extras $NO_BUILD_FLAG  # NOSONAR(S8541,S8544): ...` | Yes | Yes | The ONLY reliable placement. Used at [`python-compatibility.yml:302`](../.github/workflows/python-compatibility.yml#L302), [`python-sonarcloud.yml`](../.github/workflows/python-sonarcloud.yml) (PR #166), proven on main across multiple workflows. Comma-separated rule list accepted. |
| Preceding-line bash `#` comment inside `\|` block scalar, **with literal `--frozen` on next line** | `# NOSONAR(S8541): ...\n  uv run --frozen $NO_BUILD_FLAG ...` | Yes (apparently; see hypothesis) | N/A (no S8544 fires when literal `--frozen` present) | Used at [`python-compatibility.yml:336-337`](../.github/workflows/python-compatibility.yml#L336-L337); appears to work because the line itself is otherwise clean. Fragile; prefer single-line shape. |
| Preceding-line bash `#` comment inside `\|` block scalar, **with dynamic `$FROZEN_FLAG`** | `# NOSONAR(S8541,S8544): ...\n  uv run $FROZEN_FLAG $NO_BUILD_FLAG ...` | Not tested in isolation | **NOT honored** | Attempted at [`python-fips-compatibility.yml:209-210` and `:219-220`](../.github/workflows/python-fips-compatibility.yml#L209) in PR #157 commit `e797676`. SonarCloud continued to flag both S8541 and S8544. |
| **Inline-trailing NOSONAR inside `\|` block scalar** (NEW Wave 1C 2026-05-26) | `uv sync --all-extras --frozen $NO_BUILD_FLAG  # NOSONAR(S8541)` inside a `run: \|` multi-line block | **NOT honored** | **NOT honored** | Attempted at PR #166 commit `bb31ec1`: three `uv sync` lines with comma-separated inline-trailing NOSONAR inside a `run: \|` block. Gate stayed ERROR with 5 vulns. Fix required structural rewrite to single-line `run:` shape. |

**Rule of thumb (strengthened 2026-05-26)**: **Only single-line `run:` shape reliably honors NOSONAR.** Any placement (preceding-line OR inline-trailing) inside a `run: |` block scalar is unreliable for the `githubactions` ruleset. When you need to suppress S8541/S8544:

1. **Preferred:** Restructure the step so the `uv` invocation is the entire value of a single-line `run:` field. Use Pattern A inline.
2. **If multi-line shell logic is unavoidable:** Ensure the `uv` lines have literal `--frozen` (the literal alone often satisfies S8544 without any NOSONAR), and treat preceding-line `# NOSONAR(S8541)` as best-effort. Verify the SonarCloud gate per PR; do not assume the suppression took effect.
3. **For dynamic flag selection** (e.g. uv-locked vs uv-no-lock): split into two `if:`-guarded steps, each single-line, each with literal flags and inline Pattern A.

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

## Hypothesis (strengthened by Wave 1C empirical findings 2026-05-26)

The original hypothesis (preceding-line NOSONAR unreliable when the line uses dynamic flags) has been strengthened by additional empirical evidence: **no NOSONAR placement inside a `run: |` block scalar is reliable, regardless of literal vs dynamic flags or position (preceding vs inline-trailing).**

The supporting evidence comes from PR #166 (Wave 1C of the CI Repair Sprint), which iterated three times to converge on a passing gate:

1. **Commit `556a09f`:** split-install pattern with literal `--frozen` on `uv-locked` path and preceding-line `# NOSONAR(S8541)`; `uv-no-lock` path used multi-line `run: |` with preceding-line `# NOSONAR(S8541,S8544)`. Gate ERROR (5 vulns).
2. **Commit `bb31ec1`:** moved NOSONAR from preceding-line to inline-trailing on each `uv sync` line inside the same `run: |` block. Gate still ERROR (5 vulns). This is the new finding: inline-trailing inside a block scalar is also ignored.
3. **Commit `251ba35`:** extracted a `Resolve extras flag` step that emits `steps.extras.outputs.flag`, then collapsed both install steps to single-line `run:` with inline NOSONAR (Pattern A). Gate OK, vulns 0.

Three candidate explanations, all consistent with the evidence:

1. **The `githubactions` rule set lexes each command line inside `run: |` in isolation** and does not associate adjacent comment lines (above or trailing) with the command. Only when the entire `run:` value is a single shell expression does the NOSONAR comment lex as belonging to the same logical line.
2. **SonarCloud's `githubactions` ruleset may apply NOSONAR at the YAML-field level, not the shell-line level.** The single-line `run:` shape exposes the comment to the YAML parser; the multi-line block scalar buries it.

Comma-separated rule-list syntax was initially suspected as a third candidate, but Wave 1C tested both `# NOSONAR(S8541,S8544)` and `# NOSONAR S8541` forms inside `run: |` blocks and neither was honored. The syntax form is not the variable; placement inside a block scalar is.

The practical implication has changed: **do not rely on NOSONAR inside `run: |` blocks for any rule combination.** Restructure to single-line `run:` (Pattern A) or accept the gate failure and document it.

Lines `python-compatibility.yml:336-337` (preceding-line inside `run: |` with literal `--frozen` for S8541) still pass on main. The conservative interpretation: when the line itself is structurally safe (literal `--frozen` prevents S8544 from firing at all), the unhonored S8541 suppression doesn't matter because S8541 may not have fired in the first place. Treat this as an incidental pass, not a reliable pattern.

---

## Recommended patterns

**Pattern A (preferred): use inline NOSONAR on the YAML `run:` line**

```yaml
- name: Install dependencies (uv without lockfile)
  if: steps.detect.outputs.state == 'uv-no-lock'
  run: uv sync --all-extras $NO_BUILD_FLAG  # NOSONAR(S8541,S8544): --no-build opt-out via `no-build` input; no uv.lock by design on this path
```

This places the NOSONAR on the same physical YAML line as the offending command. SonarCloud's parser handles it predictably and accepts comma-separated rule lists. Use this when the entire command fits on one line.

**Pattern B (fragile; use only when single-line shape is impossible): preceding-line NOSONAR with literal flags**

```yaml
run: |
  # NOSONAR(S8541): --no-build is opt-out via `no-build` workflow input
  uv run --frozen $NO_BUILD_FLAG python "$SCRIPT_PATH" \
    --arg-a \
    --arg-b
```

Requires that an install step run before this block so `uv.lock` exists and `--frozen` is structurally safe. The literal `--frozen` in the command prevents S8544 from firing structurally; the preceding-line `# NOSONAR(S8541)` is best-effort suppression for `--no-build` (which is dynamic via `$NO_BUILD_FLAG`).

**Wave 1C strengthened guidance:** Even Pattern B's preceding-line suppression may not be honored by SonarCloud's `githubactions` ruleset. The line below appears to pass because the literal `--frozen` keeps S8544 from firing AND S8541 may also not fire for reasons that aren't fully understood. Treat any successful Pattern B placement as an incidental pass. **Always verify the SonarCloud quality gate per PR; do not assume the suppression took effect.**

**Anti-patterns (avoid): any NOSONAR inside `run: |` blocks**

Two empirically confirmed anti-patterns, both inside `run: |` block scalars:

1. **Preceding-line NOSONAR with dynamic `$FROZEN_FLAG`** (PR #157 commit `e797676`):

   ```yaml
   run: |
     # NOSONAR(S8541,S8544): --no-build via input; --frozen via FROZEN_FLAG
     uv run $FROZEN_FLAG $NO_BUILD_FLAG python "$SCRIPT_PATH"
   ```

2. **Inline-trailing NOSONAR on each line inside `run: |`** (PR #166 commit `bb31ec1`):

   ```yaml
   run: |
     uv sync --all-extras --frozen $NO_BUILD_FLAG  # NOSONAR(S8541)
     uv sync --all-extras $NO_BUILD_FLAG  # NOSONAR(S8541,S8544)
   ```

Both leave SonarCloud flagging the rules. The structural fix for both is identical: restructure to single-line `run:` (Pattern A) by splitting into `if:`-guarded steps and/or extracting flag-computation into output-emitting helper steps.

---

## Restructuring to expose a literal `--frozen`

The most reliable way to suppress S8544 is to remove the dynamic flag entirely. Two structural options:

**Option 1: add install step before run step.** The install step handles the locked/no-lock branching; the run step assumes `uv.lock` exists and uses literal `--frozen`. This is the approach `python-compatibility.yml` uses. Cost: ~1-2 minutes of install runtime per CI job that previously skipped it.

**Option 2: collapse to single-line run command + inline NOSONAR.** Rewrite `uv run $FROZEN_FLAG $NO_BUILD_FLAG python "$SCRIPT_PATH" \\ $A \\ $B` as a single YAML line, then add `# NOSONAR(S8541,S8544): ...` at the end of that line. Cost: line-length warnings from yamllint if the command is long; reduced readability.

For PR #157, Option 1 was selected to mirror the sibling pattern exactly. For PR #166 (Wave 1C), a third option was required because the workflow already had upstream flag-computation logic that could not be cleanly inlined:

**Option 3 (PR #166 pattern): extract flag computation into an output-emitting helper step, then collapse to single-line `run:`.** When the workflow needs to derive a flag dynamically (e.g., from a workflow input that maps to `--extra` arguments), put the derivation logic in a separate step that emits `steps.<id>.outputs.<name>`, then reference it from the install step's single-line `run:`:

```yaml
- name: Resolve extras flag
  id: extras
  if: steps.detect.outputs.state == 'uv-locked' || steps.detect.outputs.state == 'uv-no-lock'
  env:
    EXTRA_DEPENDENCIES: ${{ inputs.extra-dependencies }}
  run: |
    if [ -n "$EXTRA_DEPENDENCIES" ]; then
      echo "flag=--extra $EXTRA_DEPENDENCIES" >> "$GITHUB_OUTPUT"
    else
      echo "flag=--all-extras" >> "$GITHUB_OUTPUT"
    fi

- name: Install dependencies (uv-locked)
  if: steps.detect.outputs.state == 'uv-locked'
  env:
    UV_EXTRAS: ${{ steps.extras.outputs.flag }}
  run: uv sync $UV_EXTRAS --frozen $NO_BUILD_FLAG  # NOSONAR(S8541): --no-build via input
```

**Critical: both `${{ inputs.* }}` and `${{ steps.*.outputs.* }}` must be routed through an `env:` block, never interpolated directly into a shell script.** Direct interpolation is a workflow injection vector (Trail of Bits / GitHub Actions hardening: caller-controlled strings become attacker-controlled at workflow expansion time). The actual PR #166 pattern at [`python-sonarcloud.yml:272-319`](../.github/workflows/python-sonarcloud.yml#L272-L319) carries a `#CRITICAL` RAD annotation explaining the same point; mirror that pattern, do not shortcut it.

Cost: one extra step in the job, plus an `env:` block on each step that consumes a workflow input or earlier step output. Benefit: the `uv sync` install step is single-line, inline NOSONAR works reliably, and the only remaining `run: |` block is the helper step that does not need NOSONAR suppression at all.

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
- PR that strengthened the rule (inline-trailing-inside-block also fails) and established the Option 3 helper-step refactor pattern: [#166](https://github.com/ByronWilliamsCPA/.github/pull/166)
- Related historical fix (sibling SonarCloud remediation): commit `eecbaa3b281b1a39df59466b199d1fb31f638f7f` on branch `chore/python-compatibility-detect-poetry-uv`
- Original `--no-build` input feature: [PR #112](https://github.com/ByronWilliamsCPA/.github/pull/112)
