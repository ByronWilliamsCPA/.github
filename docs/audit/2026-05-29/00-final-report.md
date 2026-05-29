# 00 - Holistic Legacy and Architecture Audit

Repo: ByronWilliamsCPA/.github
Commit: e070932 (e070932adbacf11d72cf6fab5962c9398621104c)
Date: 2026-05-29 (UTC)
Scope: read-only, repo-wide. Six subagent reports (01-06) feed this synthesis.

## 1. Repo map (Phase 0)

This is an org-level `.github` repository: community-health files plus a library of reusable GitHub Actions workflows. It ships no application code and has no package or build system.

- Languages by tracked file: 67 YAML, 55 Markdown, 19 JSON, 8 shell, 3 TOML, 2 Bats. 172 tracked files total.
- Sizes: 40 workflow files in `.github/workflows/` (~9,432 lines), 30 files in `workflow-templates/` (15 `.yml` + 15 `.properties.json`, ~2,311 lines), 8 shell scripts (~1,525 lines), ~12,315 lines of Markdown docs.
- Test framework: Bats (`tests/*.bats`), run by `.github/workflows/shell-tests.yml`. Bats helper libraries are git submodules (`tests/libs/bats-core`, `bats-support`, `bats-assert`), uninitialized on disk.
- CI: GitHub Actions. Repo-local self-CI (self-test, shell-tests, pr-validation, reuse, scorecard, codeql, security-analysis, dependency-review, sonarcloud, release-tag, sbom-nightly) is distinct from the exported `python-*` reusables.
- Static analysis configured: pre-commit (yamllint, markdownlint, commitizen, detect-secrets, trufflehog, local `no-em-dash`), qlty (shellcheck, trivy, trufflehog, actionlint, ripgrep), Renovate, Codecov, SonarCloud.
- Runtime targets: real Python matrices bottom out at 3.10 (no EOL 3.8/3.9 anywhere); 3.13 is current. One template matrix lists an unreleased 3.14.
- Age and churn: 50 commits, first 2026-05-16, last 2026-05-28. The repo is roughly two weeks old. Most-churned files are `CHANGELOG.md` (17), `python-security-analysis.yml` (8), `python-ci.yml` (8), `python-sbom.yml` (7), `scorecard.yml` (6).
- Migration residue: none. No `requirements*.txt`, `setup.py`, `poetry.lock`, `Pipfile`, `pyproject.toml`, or `uv.lock` anywhere; no Dockerfile.

Subagents run: dependencies, code-quality (merged legacy patterns + maintainability, since shell is the only first-party code), architecture, security, cicd, docs. No subagent was skipped; none was over-scoped for a repo this size.

## 2. Code quality

The shell tier splits sharply by age, and the split is the story. The two newest, network-touching scripts (`update-pinned-actions.sh`, `fleet-audit-sha-pins.sh`) are well-written and carry 71 Bats tests with 191 real assertions, no skips, no no-op assertions. The other six scripts have zero tests (CQ-01). All 8 pass `bash -n` and all set `set -euo pipefail`, so the baseline is not broken, but the untested set includes the two scripts that do the most damage if wrong: `transfer-repos.sh` fires an irreversible `gh repo transfer` in a loop with no dry-run and discards the API error to `&>/dev/null`, and `sync-secrets.sh` writes secrets across repos and swallows failures to `2>/dev/null` (CQ-02). A red X with no error text is the current failure mode for both.

The weak quality signals are concentrated, not diffuse: a 302-line script that is mostly static `echo` plus 15 `bc` subshells (CQ-03), a `|| true` legacy path that the script's own comment already flags as dishonest (CQ-05), a 10-entry file list duplicated verbatim across two scripts with sync enforced only by a comment (CQ-06), and a 100-line function that re-implements the legacy loop it was meant to replace (CQ-07). Debt markers are genuinely absent: zero `TODO`/`FIXME`/`HACK`/`XXX` in code, one in a doc. The quality problem here is not rot; it is that the older operator scripts were written once and never given the test or error-handling discipline the newer scripts received.

## 3. Architecture

The architecture works against maintainers in exactly one place, and it is structural. The repo ships two parallel Python workflow sets: 22 reusable `workflow_call` workflows in `.github/workflows/python-*.yml`, and 15 gallery templates in `workflow-templates/`. The intended layering is reusable = implementation, template = thin caller. That holds for 9 of 15 templates. It breaks for the rest, which re-implement entire jobs inline (`python-ci` template has 5 `runs-on` jobs and zero reusable calls) so the same logic lives twice and drifts (ARCH-02, ARCH-03). One template is worse than duplicated: `workflow-templates/python-slsa.yml:73` calls `.github/workflows/python-slsa.yml` as a reusable, but that file declares only `on: workflow_dispatch` and exposes no `workflow_call` trigger (ARCH-01). Any repo adopting that template fails at workflow load. This is the single Critical finding and the clearest case of structure shipping a broken contract to consumers.

Two lower-grade structural drifts compound it. Constants are centralized for action SHAs (uniform: harden-runner 88 uses / 1 SHA, checkout 60 / 1) but scattered for Python versions (three different literal lists across five files, ARCH-04), so the one dimension most likely to change is the one with no single source. And naming relies on a `python-` prefix to separate the repo's own CI from its exported reusables in the same directory (`reuse.yml` vs `python-reuse.yml`, `scorecard.yml` vs `python-scorecard.yml`), an undocumented convention that invites editing the wrong file (ARCH-06). ADRs do not cover the decisions that matter: there are two different ADR-001 files in two directories, the index lists only one and disagrees with it on status, and neither the template/reusable split nor the SHA-pinning strategy has an ADR at all (ARCH-07).

## 4. Cross-cutting themes

Four root causes recur across domains.

The library has no released version, and everything downstream of that fact is broken or contradictory. There are zero git tags, yet the README, USAGE_EXAMPLES.md, and most doc pages tell callers to pin `@v1` (DOC-01), CHANGELOG says there are no numbered releases (a direct contradiction), self-referential security workflows are pinned to a SHA commented `# main` because no tag exists (SEC-04), and Renovate is configured to track a `v1` tag that is not there. The single highest-leverage fix in the repo is to cut and maintain the `v1` tag; it resolves a High doc defect and removes the contradiction that makes every quickstart fail.

The deliverable (templates for consumers) is held to a lower bar than the repo's own code. The one floating `@master` action pin, the non-blocking quality gate, the unreleased 3.14 matrix, and the inline-reimplemented jobs all live in `workflow-templates/`, not in the consumed reusables. The repo guards its own runs well and ships its weaker copy to others. The `@master` pin is the cleanest example: production pins that exact action to a SHA; the template a consumer copies pins it to a branch (SEC-01 / DEP-01, the same defect both agents found).

Local enforcement is strong; CI enforcement has a hole. The mandatory checks (yamllint, markdownlint, the `no-em-dash` guard, detect-secrets, commitizen) run only as pre-commit hooks. No repo-local CI workflow runs any of them, and the one workflow that could (`python-precommit.yml`) is `workflow_call`-only and skips when there is no `pyproject.toml`, which is always, here (CICD-01). A contributor who has not installed pre-commit can push em-dashes and lint failures green. Tooling config drift sits on top: two yamllint configs (one dead) and two shellcheck configs that gate at different severities (CICD-02, CICD-03).

Point-in-time working notes are committed as durable docs. Files dated 2025-01-07 and 2025-12-06 with "COMPLETE" status badges read as current reference (DOC-07), and policy text (SHA-pin rules, the model table) is duplicated across four or five instruction files that will drift (DOC-08). This is the residue of fast, AI-assisted scaffolding: a lot of documentation produced quickly, not all of it pruned.

### Resolved overlaps

- The `@master` pin was raised by both dependencies (DEP-01, High) and security (SEC-01, Medium). The security framing is better supported: the ref lives in a template, is not consumed by this repo's own runs, and gates a report-only Sonar step, so it does not threaten this repo's supply chain directly. It does propagate an unpinned ref to every consumer, which keeps it above Low. Carried once as SEC-01 (Medium).
- The 3.14 matrix appears in DEP-03 (the unreleased-version defect) and inside ARCH-03 (the broader template-vs-reusable drift). Kept as two findings because the fixes differ: drop/flag 3.14 versus repoint the template at the reusable. ARCH-04 is the general form (no central version source).
- CLAUDE.md's claim that the Bats suite covers `update-pinned-actions.sh` and `fleet-audit-sha-pins.sh` is accurate (verified by code-quality); ARCH-08 is the separate point that CLAUDE.md omits the other five scripts. Not a contradiction.
- DEP-02 (submodules uninitialized) and DOC-10 (CONTRIBUTING does document `git submodule update --init`) are complementary: the init step is documented, so the residual risk is the missing branch/ref discipline and the local/CI init dependency, not a missing instruction.

## 5. Prioritized remediation backlog

Sorted by severity, then effort. Effort: S under a day, M a few days, L a week or more. The same rows appear in `findings.json` and `findings.csv` with identical IDs, severities, and efforts.

| ID | Finding | Domain | Severity | Effort | Files |
|----|---------|--------|----------|--------|-------|
| ARCH-01 | python-slsa template calls a reusable that has no workflow_call trigger | architecture | Critical | S | workflow-templates/python-slsa.yml;<br>.github/workflows/python-slsa.yml |
| DEP-02 | Git submodules unpinned in .gitmodules and uninitialized | dependencies | High | S | .gitmodules;<br>tests/libs/bats-core;<br>tests/libs/bats-support;<br>(+1 more) |
| DOC-02 | Malformed uses: path in python-fips-compatibility doc | docs | High | S | docs/workflows/python-fips-compatibility.md |
| ARCH-02 | Five templates re-implement steps instead of calling the reusables | architecture | High | M | workflow-templates/python-ci.yml;<br>workflow-templates/python-security-analysis.yml;<br>workflow-templates/python-docs.yml;<br>(+2 more) |
| ARCH-03 | Template python-ci drifts from the reusable on Python versions and jobs | architecture | High | M | workflow-templates/python-ci.yml;<br>.github/workflows/python-ci.yml |
| CICD-01 | Pre-commit lint hooks are enforced in no repo-local CI | cicd | High | M | .pre-commit-config.yaml;<br>.github/workflows/self-test.yml;<br>.github/workflows/pr-validation.yml;<br>(+1 more) |
| CQ-02 | Untested destructive operator scripts swallow per-repo errors | code-quality | High | M | scripts/transfer-repos.sh;<br>scripts/sync-secrets.sh |
| DOC-01 | @v1 references are unresolvable; zero git tags exist; contradicts CHANGELOG | docs | High | M | README.md;<br>USAGE_EXAMPLES.md;<br>docs/workflows;<br>(+1 more) |
| CQ-01 | Six of eight shell scripts have zero test coverage | code-quality | High | L | scripts/calculate-image-storage.sh;<br>scripts/check-no-em-dash.sh;<br>scripts/regenerate-checksums.sh;<br>(+3 more) |
| ARCH-06 | Naming collision risk: repo-local CI vs reusable exports in one dir | architecture | Medium | S | .github/workflows/reuse.yml;<br>.github/workflows/python-reuse.yml;<br>.github/workflows/scorecard.yml;<br>(+2 more) |
| ARCH-07 | Duplicate ADR-001 across two dirs; major decisions undocumented | architecture | Medium | S | docs/architecture/adr-001-scorecard-publish-results.md;<br>docs/planning/adr/adr-001-workflow-security-remediation-delivery.md;<br>docs/architecture/adr-000-index.md |
| CICD-02 | Two yamllint configs disagree; .yamllint.yml is dead | cicd | Medium | S | .yamllint;<br>.yamllint.yml |
| CICD-03 | Two shellcheck configs not aligned; qlty and CI gate at different severities | cicd | Medium | S | .shellcheckrc;<br>.qlty/configs/.shellcheckrc;<br>.qlty/qlty.toml;<br>(+1 more) |
| CQ-05 | Failure-swallowing \|\| true in the legacy update path | code-quality | Medium | S | scripts/update-pinned-actions.sh |
| CQ-06 | Duplicated 10-entry FILES array across two scripts | code-quality | Medium | S | scripts/regenerate-checksums.sh;<br>sync_org_files.sh |
| DEP-03 | Workflow-template Python matrix targets unreleased 3.14 | dependencies | Medium | S | workflow-templates/python-ci.yml |
| DOC-03 | README links to a doc page that does not exist | docs | Medium | S | README.md;<br>docs/workflows |
| DOC-05 | README workflow catalog omits four reusables | docs | Medium | S | README.md |
| DOC-06 | Version-tag inconsistency across docs (@main vs @v1) | docs | Medium | S | docs/workflows;<br>examples;<br>USAGE_EXAMPLES.md |
| DOC-07 | Stale point-in-time working notes presented as current docs | docs | Medium | S | docs/PHASE1_IMPLEMENTATION_COMPLETE.md;<br>docs/RECOMMENDED_NEXT_STEPS.md;<br>PYPI_WORKFLOW_ANALYSIS.md;<br>(+2 more) |
| SEC-01 | Floating @master action pin in the SonarQube quality-gate template | security | Medium | S | workflow-templates/python-sonarcloud.yml |
| ARCH-04 | Python-version lists scattered as literals with no central source | architecture | Medium | M | .github/workflows/python-ci.yml;<br>workflow-templates/python-ci.yml |
| CQ-03 | calculate-image-storage.sh is 302 lines, mostly static prints plus 15 bc calls | code-quality | Medium | M | scripts/calculate-image-storage.sh |
| DOC-04 | Per-workflow doc coverage is 14 of 23 reusables | docs | Medium | M | docs/workflows |
| ARCH-08 | CLAUDE.md understates the script and test surface | architecture | Low | S | .claude/CLAUDE.md;<br>scripts |
| CICD-04 | Coverage and Sonar gates target a package this repo does not have | cicd | Low | S | .codecov.yml;<br>sonar-project.properties;<br>.github/workflows/sonarcloud.yml |
| CICD-05 | setup-python steps lack cache where not uv-backed | cicd | Low | S | .github/workflows/python-docs.yml;<br>.github/workflows/python-fuzzing.yml;<br>.github/workflows/python-sbom.yml;<br>(+2 more) |
| CICD-06 | reuse.yml lacks concurrency control | cicd | Low | S | .github/workflows/reuse.yml |
| CQ-04 | Unquoted $total_size argument | code-quality | Low | S | scripts/calculate-image-storage.sh |
| CQ-08 | Orphaned test fixture test-unpinned.yml | code-quality | Low | S | tests/fixtures/workflows/test-unpinned.yml |
| CQ-09 | Idiom inconsistency, [ ] vs [[ ]] and echo vs printf | code-quality | Low | S | scripts/transfer-repos.sh;<br>scripts/sync-secrets.sh;<br>scripts/calculate-image-storage.sh;<br>(+1 more) |
| DEP-05 | Pre-commit hooks SHA-pinned but absent from Renovate managers | dependencies | Low | S | .pre-commit-config.yaml;<br>renovate.json |
| DOC-08 | Instruction-file policy duplicated across four to five files | docs | Low | S | AGENTS.md;<br>GEMINI.md;<br>.claude/CLAUDE.md;<br>(+1 more) |
| SEC-02 | SonarQube quality gate is non-blocking | security | Low | S | workflow-templates/python-sonarcloud.yml |
| SEC-03 | Container scan SARIF/login use continue-on-error; vuln gate is opt-in | security | Low | S | .github/workflows/python-container-security.yml |
| SEC-04 | Self-referential security workflows pinned via a mutable # main comment | security | Low | S | .github/workflows/security-analysis.yml;<br>.github/workflows/scorecard.yml |
| CQ-07 | pin_tags_main is a 100-line function duplicating the legacy loop | code-quality | Low | M | scripts/update-pinned-actions.sh |

Clean areas, recorded once: action SHA pinning is uniform with no drift across all 34 workflow files; every one of 51 workflow files carries a top-level `permissions:` block (37 deny-all `{}`) with no `write-all` and no `pull_request_target`; no script injection (untrusted `github.event.*` reaches `run:` only via `env:` indirection); no hardcoded secrets and a clean `.secrets.baseline` with no drift; no deprecated Action mechanics (`::set-output`, Node12/16, artifact v1-v3 all absent); no migration residue; zero in-code debt markers.

## 6. Verdict

Drifting, not at-risk. The security and supply-chain fundamentals are in place and the repo is too young (two weeks, 50 commits) to have rotted; what it has is the drift of fast scaffolding that outran its own conventions. One Critical (a template that fails to load for any adopter), eight High, and a cluster of contradictions that all trace back to four root causes.

The three changes that move it most:

1. Cut and maintain the `v1` tag (DOC-01, with SEC-04 and the Renovate `v1` follow), so the documented usage actually resolves and the CHANGELOG stops contradicting the README.
2. Fix the template tier as a deliverable: repair the broken `python-slsa` caller (ARCH-01), convert the inline templates to thin callers (ARCH-02, ARCH-03), and pin the `@master` ref (SEC-01).
3. Enforce the mandatory checks in repo-local CI (CICD-01) and add tests for the destructive operator scripts (CQ-02, CQ-01), so the rules the repo states for everyone else are gated on its own pushes.
