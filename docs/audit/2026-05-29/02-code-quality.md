# 02 - Code Quality and Legacy Patterns

Scope: 7 scripts in `scripts/` plus `sync_org_files.sh` (1525 lines), and 2 Bats suites (71 tests). All 8 scripts pass `bash -n` and all carry `set -euo pipefail`. The two newest, network-touching scripts (`update-pinned-actions.sh`, `fleet-audit-sha-pins.sh`) are well-tested and defensively written; the older operator scripts (`transfer-repos.sh`, `sync-secrets.sh`, `calculate-image-storage.sh`) are untested and carry the bulk of the quality debt. HEAD e070932.

---

**CQ-01: Six of eight scripts have zero test coverage**
Severity: High. Effort: L (writing Bats suites with `gh`/`docker`/`curl` stubs for 6 scripts, plus fixtures).
Evidence: `tests/` has only `update-pinned-actions.bats` (50 `@test`) and `fleet-audit-sha-pins.bats` (21 `@test`). No suite exists for `calculate-image-storage.sh`, `check-no-em-dash.sh`, `regenerate-checksums.sh`, `sync-secrets.sh`, `transfer-repos.sh`, or `sync_org_files.sh`. CLAUDE.md claim that the Bats suite covers `update-pinned-actions.sh` and `fleet-audit-sha-pins.sh`: verified correct. `.github/workflows/shell-tests.yml` runs `tests/*.bats`, so any new suite is auto-included.
Recommendation: Prioritize coverage for the two scripts that mutate state at scale, `transfer-repos.sh` (irreversible repo transfers) and `sync_org_files.sh` (writes verified files into downstream repos); both are stubbable the same way the existing suites stub `gh`/`curl`.

**CQ-02: `transfer-repos.sh` and `sync-secrets.sh` are untested and perform destructive/sensitive operations**
Severity: High. Effort: M.
Evidence: `scripts/transfer-repos.sh:112` fires `gh api repos/.../transfer -X POST` (irreversible) inside a loop with no dry-run mode; `scripts/sync-secrets.sh:103-105` writes secrets to every Python repo. Both swallow per-repo failures into a counter (`transfer-repos.sh:112` `&>/dev/null`, `sync-secrets.sh:105` `2>/dev/null`) so the actual API error is never surfaced, only a red X. First committed 2026-05-16; no tests since.
Recommendation: Add a `--dry-run` flag to `transfer-repos.sh` and capture+print the failing `gh` stderr instead of discarding it; add Bats coverage gating the confirmation and skip paths.

**CQ-03: `calculate-image-storage.sh` is the longest script and is largely a hardcoded print block**
Severity: Medium. Effort: M.
Evidence: 302 lines (`scripts/calculate-image-storage.sh`), of which lines 71-73, 236-300 are static banner/recommendation `echo` output. 91 `echo` calls. 15 `bc -l` subshell invocations for arithmetic (lines 47-65, 105-147, 267, 294) where bash integer math or a single awk pass would do. No tests; `--all`/`--local`/`--repo` mode dispatch (lines 80, 157) is unverified.
Recommendation: Extract the static pricing/recommendation text to a heredoc or data file and collapse the per-unit `bc` calls; only then is the script small enough to test cheaply.

**CQ-04: Unquoted argument in `calculate-image-storage.sh`**
Severity: Low. Effort: S.
Evidence: `scripts/calculate-image-storage.sh:129` `$(bytes_to_human $total_size)` passes `$total_size` unquoted. Harmless today (always an integer), but inconsistent with the quoting used everywhere else and a latent word-split bug if the value ever holds whitespace.
Recommendation: Quote it: `"$total_size"`.

**CQ-05: Failure-swallowing `|| true` in the legacy update path**
Severity: Medium. Effort: S.
Evidence: 10 `|| true` occurrences in `scripts/update-pinned-actions.sh` (lines 275, 365, 395, 403, 409, 418, 424, 430, plus two `2>/dev/null || true`). The `((VAR++)) || true` cases (409, 418, 424, 430) are the standard `set -e` arithmetic-returns-1 guard and are benign. The `gh release list ... 2>/dev/null || true` cases (275, 395, 403) and the `grep ... > "$UNIQUE_ACTIONS_FILE" || true` (365) silently mask real API/grep failures; the script's own comment at line 169 calls out that the old `{ ...; } || true` form "conflated both into silent success, which contradicts the script's audit-honesty goal," yet the legacy main path (lines 362-365, 392-405) still uses exactly that pattern, while the newer `extract_tag_pins`/`extract_branch_pins` functions (lines 165-233) correctly capture rc.
Recommendation: Apply the same rc-aware grep/gh capture pattern from `extract_tag_pins` to the legacy main flow so a rate-limit or unreadable-dir failure is not reported as "up to date."

**CQ-06: Duplicated FILES array across two scripts (manual sync hazard)**
Severity: Medium. Effort: S.
Evidence: The 10-entry sync list is duplicated verbatim in `scripts/regenerate-checksums.sh:17-28` and `sync_org_files.sh:32-43`. `regenerate-checksums.sh:12` documents "The file list MUST stay in sync with FILES in sync_org_files.sh" but nothing enforces it; the two arrays drifting silently breaks checksum verification.
Recommendation: Source the list from one file (a shared `FILES` array file sourced by both) or add a test asserting the two arrays are identical.

**CQ-07: `pin_tags_main` is a 100-line function mixing extraction, reporting, and apply**
Severity: Low. Effort: M.
Evidence: `scripts/update-pinned-actions.sh:238-338` (`pin_tags_main`, ~100 lines) and the legacy top-level loop at lines 377-433 (~56 lines) duplicate the same shape: resolve repo/major, query `gh release list` with an identical jq expression (lines 273-275 vs 393-395), resolve SHA, build a `sed s|...|...|g` substitution (lines 332 vs 488). Two near-identical sed-escaping blocks (lines 300-326 vs 482-483) are a known maintenance trap, flagged in-code at lines 309-311.
Recommendation: Factor the shared "latest tag within major -> SHA" lookup and the sed-substitution builder into helpers used by both modes; this also shrinks the untested legacy path.

**CQ-08: Orphaned test fixture `test-unpinned.yml`**
Severity: Low. Effort: S.
Evidence: `tests/fixtures/workflows/test-unpinned.yml` (20 lines) is referenced by no `@test` in either suite (`git grep test-unpinned tests/` returns nothing). Dead fixture; the "does not count @v3 / unpinned" assertion at `update-pinned-actions.bats:312-317` relies on the inline fixtures, not this file.
Recommendation: Either wire it into an explicit unpinned-detection test or remove it.

**CQ-09: Idiom inconsistency, `[ ]` vs `[[ ]]` and `echo` vs `printf`**
Severity: Low. Effort: S.
Evidence: The two tested scripts use `[[ ]]` throughout; the older scripts mix in `[ ]` (`transfer-repos.sh:50,65,134,138,156`; `sync-secrets.sh:48,63,73,119`; `calculate-image-storage.sh:163,169,261,294`; `regenerate-checksums.sh:33,37`). No backticks in code (all `` ` `` hits are comments/heredoc text). No `read` without `-r`. Em-dash usage: none in scripts (the repo's own `check-no-em-dash.sh` hook enforces this).
Recommendation: Cosmetic; standardize on `[[ ]]` opportunistically when these scripts are next touched. No correctness impact (all current `[ ]` operands are quoted).

**Clean sub-areas (one line each):**
- TODO/FIXME/HACK/XXX debt: zero in scripts and YAML; one occurrence in a doc (`docs/migration/image-detection-pypi-migration.md`). Orchestrator's non-doc count of 0 confirmed.
- Syntax: all 8 scripts pass `bash -n`.
- `set -euo pipefail`: present in all 8 scripts.
- Dead/commented-out code / resolved feature flags: none found in scripts (only the orphaned fixture, CQ-08).
- Test assertion quality: no `skip` calls, no empty/no-op `@test`s; 191 real assertions (`assert_success` 63, `assert_output` 55, `assert_failure` 10, plus `refute_output`); STRICT_AUDIT exit code checked explicitly (`fleet-audit-sha-pins.bats:296,317,381`).

---

## Backlog rows (for orchestrator)

| ID | title | domain | severity | effort | files | evidence | recommendation | cve |
|----|-------|--------|----------|--------|-------|----------|----------------|-----|
| CQ-01 | Six of eight scripts have zero test coverage | code-quality | High | L | scripts/calculate-image-storage.sh, scripts/check-no-em-dash.sh, scripts/regenerate-checksums.sh, scripts/sync-secrets.sh, scripts/transfer-repos.sh, sync_org_files.sh | only 2 Bats suites (71 tests) cover update-pinned-actions.sh + fleet-audit-sha-pins.sh; shell-tests.yml runs tests/*.bats | Add Bats suites starting with transfer-repos.sh and sync_org_files.sh | |
| CQ-02 | Untested destructive/sensitive operator scripts swallow errors | code-quality | High | M | scripts/transfer-repos.sh, scripts/sync-secrets.sh | transfer-repos.sh:112 irreversible transfer with &>/dev/null; sync-secrets.sh:105 secret write with 2>/dev/null; no dry-run | Add --dry-run, surface gh stderr, add coverage | |
| CQ-03 | calculate-image-storage.sh is 302 lines, mostly static prints + 15 bc calls | code-quality | Medium | M | scripts/calculate-image-storage.sh | 302 lines; 91 echo; 15 bc -l (lines 47-65,105-147,267,294); untested mode dispatch | Extract static text to heredoc, collapse bc math, then test | |
| CQ-04 | Unquoted $total_size argument | code-quality | Low | S | scripts/calculate-image-storage.sh | line 129 $(bytes_to_human $total_size) unquoted | Quote as "$total_size" | |
| CQ-05 | Failure-swallowing \|\| true in legacy update path | code-quality | Medium | S | scripts/update-pinned-actions.sh | lines 365,395,403 mask grep/gh failures; contradicts in-code note at line 169 | Apply rc-aware capture from extract_tag_pins to legacy flow | |
| CQ-06 | Duplicated 10-entry FILES array across two scripts | code-quality | Medium | S | scripts/regenerate-checksums.sh, sync_org_files.sh | identical arrays at regenerate:17-28 and sync_org_files:32-43; sync enforced only by comment | Source from one shared file or add equality test | |
| CQ-07 | pin_tags_main 100-line function duplicates legacy loop logic | code-quality | Low | M | scripts/update-pinned-actions.sh | lines 238-338 vs 377-433; duplicate jq (273-275/393-395) and sed-escape (300-326/482-483) blocks | Factor shared latest-tag-to-SHA and sed-builder helpers | |
| CQ-08 | Orphaned test fixture test-unpinned.yml | code-quality | Low | S | tests/fixtures/workflows/test-unpinned.yml | referenced by no @test (git grep empty) | Wire into an unpinned-detection test or remove | |
| CQ-09 | Idiom inconsistency [ ] vs [[ ]] and echo vs printf | code-quality | Low | S | scripts/transfer-repos.sh, scripts/sync-secrets.sh, scripts/calculate-image-storage.sh, scripts/regenerate-checksums.sh | older scripts use [ ] (transfer:50,65,134,138,156 etc); no correctness impact | Standardize on [[ ]] opportunistically | |
