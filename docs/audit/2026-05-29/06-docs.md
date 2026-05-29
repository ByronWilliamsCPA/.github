# 06 - Documentation and Developer Experience

Docs are broad and well structured, but the public usage surface is built on version tags that do not exist: the repo has zero git tags, yet README, USAGE_EXAMPLES.md, and most docs/workflows pages tell callers to pin `@v1`, while CHANGELOG.md states there are no numbered releases. Coverage is also uneven: 23 `python-*.yml` reusables exist but only 14 have a docs/workflows page, README mentions 19 of 23 and links to one doc page that does not exist, and one doc page ships a malformed `uses:` path. Root-level analysis docs read as point-in-time working notes rather than durable reference.

**DOC-01: `@v1` references are unresolvable; no git tags exist**
Severity: High | Effort: M (decide tag/release policy, then sweep or pin)
Evidence: `git tag | wc -l` returns `0`. README.md:114,147 and ~30 lines in USAGE_EXAMPLES.md (lines 19,45,63,...,488) plus docs/workflows pages use `@v1`. CHANGELOG.md:7-9 says "date-based version headers ... there are no numbered releases." A caller copying any quickstart gets a workflow-resolution failure because `@v1` resolves to nothing.
Recommendation: Pick one: (a) create and maintain a `v1` moving tag (and document it), or (b) change all examples to `@main` with a pinned-SHA note. Reconcile CHANGELOG.md:7-9 with whichever is chosen. This is the single highest-impact doc defect.

**DOC-02: Malformed `uses:` path in python-fips-compatibility.md**
Severity: High | Effort: S
Evidence: docs/workflows/python-fips-compatibility.md:42,53,99 use `ByronWilliamsCPA/.github/workflows/python-fips-compatibility.yml@v1`, missing the repo `.github` segment. Every other doc uses `ByronWilliamsCPA/.github/.github/workflows/...`. The shown path does not resolve.
Recommendation: Fix to `ByronWilliamsCPA/.github/.github/workflows/python-fips-compatibility.yml`.

**DOC-03: README links to a doc page that does not exist**
Severity: Medium | Effort: S
Evidence: README.md:82 links `[Qlty Coverage](docs/workflows/python-qlty-coverage.md)`; that file is absent (`ls docs/workflows/` shows no python-qlty-coverage.md). The workflow `.github/workflows/python-qlty-coverage.yml` exists.
Recommendation: Write the doc page or repoint the link to the workflow file.

**DOC-04: Per-workflow doc coverage 14/23; several reusables undocumented**
Severity: Medium | Effort: M
Evidence: 23 `python-*.yml` reusables; docs/workflows has 14 matching `python-*.md` pages (plus README, NEW_WORKFLOWS_SUMMARY, workflow-optimizations). No doc page for: python-pr-validation, python-precommit, python-qlty-coverage, python-release, python-reuse, python-sbom, python-scorecard, python-security-analysis, python-slsa (9 missing). (Orchestrator's "15 pages / ~17 reusables" undercounts; actual is 14/23.)
Recommendation: Add stub pages for the 9 uncovered reusables, prioritizing release/publish/security ones users will call directly.

**DOC-05: README workflow catalog omits 4 reusables**
Severity: Medium | Effort: S
Evidence: README.md:76-94 lists workflows; no mention of python-pr-validation, python-precommit, python-slsa, python-standard-stack (the latter has its own doc page docs/workflows/python-standard-stack.md). 19 of 23 reusables appear.
Recommendation: Add the 4 missing entries to the README catalog.

**DOC-06: Version-tag inconsistency across docs (`@main` vs `@v1`)**
Severity: Medium | Effort: S (folds into DOC-01)
Evidence: docs/workflows examples mix tags: `@main` in python-docs.md:21, python-docker.md:44, python-container-security.md:37, python-compatibility.md:31, python-mutation.md:25, python-performance-regression.md:41, python-standard-stack.md:30, python-supplemental-checks.md:41, and all examples/*.yml; `@v1` in python-fuzzing.md, python-sonarcloud.md, python-publish-pypi.md, python-fips-compatibility.md, workflow-optimizations.md. USAGE_EXAMPLES.md:225 is `@main` while the rest are `@v1`.
Recommendation: Standardize on the DOC-01 decision repo-wide.

**DOC-07: Stale point-in-time working notes presented as current docs**
Severity: Medium | Effort: S (archive/move)
Evidence: docs/PHASE1_IMPLEMENTATION_COMPLETE.md:3-7 ("Date: 2025-01-07", "Status: COMPLETE", emoji status badges); docs/RECOMMENDED_NEXT_STEPS.md:3 ("Date: 2025-01-07", "Estimated Total Effort: 4 hours for Phase 1"); PYPI_WORKFLOW_ANALYSIS.md:3-4 ("Status: Complete", "Date: 2025-12-06"); docs/ENHANCEMENT_IMPLEMENTATION_ANALYSIS.md, docs/planning/*. These describe completed/proposed work as project status, not reusable reference, and will mislead readers about current state.
Recommendation: Move to a docs/archive/ or docs/history/ area, or convert to dated audit entries; keep QLTY_INTEGRATION.md (reads as a durable how-to).

**DOC-08: Instruction-file content duplicated across 4-5 files**
Severity: Low | Effort: S
Evidence: SHA-pinning policy appears in GEMINI.md, .claude/CLAUDE.md, .github/copilot-instructions.md; model-selection table in AGENTS.md and .claude/CLAUDE.md. Five instruction files (AGENTS.md 24, GEMINI.md 21, .claude/CLAUDE.md 50, .github/copilot-instructions.md 23 lines) restate overlapping policy. Drift risk when one is updated.
Recommendation: Make one canonical file (AGENTS.md or .claude/CLAUDE.md) and have the others cross-reference it.

**DOC-09 (clean): CLAUDE.md cross-references resolve.** `.claude/CLAUDE.md` `../AGENTS.md`, `../docs/known-vulnerabilities.md`, `../docs/architecture/adr-000-index.md` all exist relative to repo root.

**DOC-10 (clean): CONTRIBUTING onboarding covers submodules and tests.** CONTRIBUTING.md:32 `pre-commit install`, :56 `git submodule update --init --recursive`, :57 `bats tests/`, :50 `pytest`. New shell/workflow contributors have a documented test path even though the submodules are uninitialized on disk.

**DOC-11 (clean): CHANGELOG consistent with commitizen config.** CHANGELOG.md uses Keep-a-Changelog + date-based headers; .cz.toml:1-2 sets `cz_conventional_commits` and .pre-commit-config.yaml:24-27 wires the commitizen hook. The date-versioning note (CHANGELOG.md:7-9) is internally consistent, but contradicts the `@v1` usage docs (see DOC-01).

**DOC-12 (clean): python-fuzzing.md inputs match the workflow.** doc table (python-fuzzing.md:83-88: fuzz-seconds/sanitizer/dry-run) matches `.github/workflows/python-fuzzing.yml` inputs (lines 38,44,68; consumed at 178-182). No drift in this spot-check.

## Backlog rows (for orchestrator)

| ID | title | domain | severity | effort | files | evidence | recommendation | cve |
|----|-------|--------|----------|--------|-------|----------|----------------|-----|
| DOC-01 | `@v1` refs unresolvable; zero git tags; contradicts CHANGELOG | docs | High | M | README.md, USAGE_EXAMPLES.md, docs/workflows/*.md, CHANGELOG.md | `git tag` empty; README.md:114,147; USAGE_EXAMPLES.md:19-488 `@v1`; CHANGELOG.md:7-9 "no numbered releases" | Create/maintain `v1` tag or switch examples to `@main`; reconcile CHANGELOG | |
| DOC-02 | Malformed `uses:` path in FIPS doc | docs | High | S | docs/workflows/python-fips-compatibility.md | lines 42,53,99 missing repo `.github` segment | Add the `.github/` segment | |
| DOC-03 | README links to nonexistent doc page | docs | Medium | S | README.md, docs/workflows/ | README.md:82 -> docs/workflows/python-qlty-coverage.md absent | Write page or repoint link | |
| DOC-04 | Per-workflow doc coverage 14/23 | docs | Medium | M | docs/workflows/ | 9 reusables have no page (pr-validation, precommit, qlty-coverage, release, reuse, sbom, scorecard, security-analysis, slsa) | Add stub pages, prioritize release/publish/security | |
| DOC-05 | README catalog omits 4 reusables | docs | Medium | S | README.md | README.md:76-94 missing pr-validation, precommit, slsa, standard-stack | Add entries | |
| DOC-06 | Version-tag inconsistency `@main` vs `@v1` | docs | Medium | S | docs/workflows/*.md, examples/*, USAGE_EXAMPLES.md | mixed tags listed in finding | Standardize per DOC-01 | |
| DOC-07 | Stale working-note docs presented as current | docs | Medium | S | docs/PHASE1_IMPLEMENTATION_COMPLETE.md, docs/RECOMMENDED_NEXT_STEPS.md, PYPI_WORKFLOW_ANALYSIS.md, docs/ENHANCEMENT_IMPLEMENTATION_ANALYSIS.md, docs/planning/* | dated 2025-01-07 / 2025-12-06 status docs | Archive or convert to dated audit entries | |
| DOC-08 | Duplicated policy across instruction files | docs | Low | S | AGENTS.md, GEMINI.md, .claude/CLAUDE.md, .github/copilot-instructions.md | SHA-pin in 3 files, model table in 2 | Canonicalize one, cross-reference others | |
