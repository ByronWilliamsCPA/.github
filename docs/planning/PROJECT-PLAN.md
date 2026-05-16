# Project Plan: Workflow Security and Architecture Remediation

**Date:** 2026-04-30
**Status:** Active
**ADR:** [ADR-001](adr/adr-001-workflow-security-remediation-delivery.md)
**Source Spec:** `docs/superpowers/specs/2026-04-30-workflow-security-architecture-remediation-design.md`

---

## Executive Summary

A parallel agent audit of the 23 reusable org-level GitHub Actions workflows in
`ByronWilliamsCPA/.github` identified 3 critical findings (one arbitrary Python RCE vector,
one code injection vector, one missing SLSA provenance), 6 high findings (permission
over-scoping, shell injection via unquoted inputs), and multiple medium findings spanning
egress policy, artifact integrity, and false-assurance security gates. Architecture gaps
(duplicated tooling with divergent configs, wrong org references, missing workflows) and
supply chain gaps (Docker SBOM and provenance off by default, pip-audit not used consistently)
were identified in parallel.

This plan delivers remediation in three sequential PRs, each gating on the previous merging
to `main`. Security fixes ship first, in isolation from breaking architectural changes.
Breaking changes ship second, with in-file migration notes for every affected caller. New
capabilities ship third, additive only.

---

## Scope

### In Scope

- All 23 reusable workflows in `.github/workflows/`
- Shell injection remediation: env-var isolation pattern applied to every `run:` block that
  references `${{ inputs.* }}`
- Python heredoc injection remediation: all inputs read via `os.environ` instead of direct
  interpolation
- Permission scoping: workflow-level permissions moved to the specific jobs that need them
- Supply chain: Docker SBOM and provenance defaults, pip-audit adoption, SLSA template pins
- Architecture: remove duplicated SonarCloud and Codecov from `python-ci.yml`, fix org
  references, add Scorecard score gate, hard-fail removed workflow, fix auto-merge detection
- New capabilities: `python-precommit.yml`, `python-standard-stack.yml`, commit-lint job

### Out of Scope

| Item | Reason |
| --- | --- |
| Egress policy upgrades (`audit` to `block`) across all 23 workflows | High effort; requires per-job endpoint discovery |
| Mid-job `git checkout origin/main` refactor in `python-performance-regression.yml` (MED-07) | Requires significant job-splitting redesign |
| SBOM attachment to GitHub Releases from `python-sbom.yml` | Requires `python-release.yml` coordination |
| `python-codecov.yml` `CODECOV_TOKEN: required: true` to `required: false` | Low priority |

---

## Architecture Overview

### ADR-001: Three Sequential PRs with Hard Dependency Gates (Accepted)

Security fixes, architecture cleanup, and new capabilities are delivered in strict dependency
order. Each PR merges to `main` before the next branch is created. This isolates breaking
architecture changes from security fixes and makes each PR independently reviewable.

Rejected alternative: single large PR (too wide for safe review; security and breaking changes
interact unpredictably in a combined diff).

Rejected alternative: many small PRs per finding (review overhead exceeds value; related fixes
belong together for atomic validation).

### ADR-001: Parallel Worktrees for Phase 1

Phase 1 splits into two logically independent change sets worked in parallel worktrees and
merged into the integration branch before the PR opens:

- Worktree A (`fix/perf-regression-rce`): `python-performance-regression.yml` only
- Worktree B (`fix/workflow-input-quoting`): systematic sweep across ~12 files plus supply chain

Both worktrees live at `.worktrees/<branch-slug>` inside the project root per the mandatory
convention in `.claude/rules/git-workflow.md`.

### ADR-001: Hard Removal with Migration Notes (No Deprecation Shims)

SonarCloud, Codecov, and `python-pr-validation.yml` are removed entirely rather than gated
behind deprecation flags. Breaking callers receive migration comments in workflow headers and
a hard-fail job that exits 1 with a migration message on every trigger.

Rejected alternative: deprecation path with flags kept for one release cycle (adds dead code,
complicates Phase 2, and signals that removal is negotiable).

### ADR-001: Env-Var Isolation as the Canonical Input-Sanitization Pattern

All inputs used in `run:` shell blocks or Python heredocs must be declared in an `env:` block
and referenced as `$VAR` (shell) or `os.environ["VAR"]` (Python). Direct
`${{ inputs.* }}` interpolation in `run:` blocks is prohibited. This pattern is applied
systematically in Phase 1 and is required for all new workflows in Phase 3.

### ADR-001: Supply Chain Fixes Bundled with Security PR

Docker provenance defaults, pip-audit replacement, and SLSA template fixes are
security-adjacent and deliver in Phase 1 alongside the shell-injection and Python-injection
fixes. No justification exists for deferring security posture improvements when already scoped.

---

## Technology Stack

| Layer | Technology |
| --- | --- |
| Workflow runtime | GitHub Actions (reusable `workflow_call` workflows) |
| Shell validation | actionlint, shellcheck (via `qlty check`) |
| Python toolchain | uv, pip-audit, bandit, ruff, basedpyright |
| Security hardening | step-security/harden-runner (egress audit/block) |
| Supply chain | SLSA provenance, Docker SBOM, SHA-pinned actions |
| Pre-commit | pre-commit (enforced before every commit) |
| Commit convention | Conventional Commits, signed commits |

---

## Phased Development

### Phase 1: Security Fixes and Supply Chain

**Branch:** `fix/workflow-security-remediation`
**Depends on:** none (first phase)
**Breaking:** soft (Docker `enable-sbom` default flips to `true`; callers that set it `false`
intentionally must add an explicit override)

#### Goal

Eliminate all critical and high security findings before any architectural work. No `${{ inputs.* }}`
appears unquoted in any `run:` block across all 23 workflows after this phase merges.

#### Worktree Structure

Two parallel worktrees merge into `fix/workflow-security-remediation` before the PR opens.
Worktree A merges first (smaller, easier to review), then Worktree B (resolve any conflicts).

**Worktree A** at `.worktrees/fix-perf-regression-rce` on branch `fix/perf-regression-rce`:
touches only `python-performance-regression.yml`.

**Worktree B** at `.worktrees/fix-workflow-input-quoting` on branch `fix/workflow-input-quoting`:
systematic sweep across ~12 files plus supply chain fixes.

#### Deliverables

**Worktree A:**

- Remove `synthetic-data-script` input from `python-performance-regression.yml` (CRIT-01 RCE);
  callers place their script at `scripts/generate_test_data.py`; document convention in header
- Move all Python heredoc inputs to `env:` blocks, read via `os.environ` (CRIT-02); affects
  lines 185-192, 348, 353-354, 419
- Move `benchmark-script`, `benchmark-args`, `warmup-iterations`, `benchmark-iterations` to
  env vars and quote all shell references (HIGH-05)

**Worktree B:**

- `python-ci.yml`: env-var pattern for `source-directory`, `test-directory`, `python-version`,
  `dead-code-confidence`; move `pull-requests: write` and `checks: write` from workflow level
  to job level; replace `|| true` swallowing with exit-code-5 check pattern
- `python-compatibility.yml`: env-var pattern for `operating-systems`, `python-versions`,
  `system-deps-*`; add pattern validation before sudo install
- `python-docs.yml`: move `id-token: write` to deploy job level; add harden-runner to deploy
  job with `egress-policy: block`; remove redundant `actions/cache` step
- `python-release.yml`: move all permissions to job level; remove `issues: write`; set
  workflow-level to `contents: read`; add `if: always()` to artifact upload step
- `python-security-analysis.yml`: move boolean heredoc inputs `fail-on-high`, `fail-on-medium`
  to env vars
- `python-pr-validation.yml`: env-var pattern for remaining string inputs (Phase 2 replaces
  content; Phase 1 only hardens existing inputs)
- `python-slsa.yml`: SHA-pin comment examples; add prominent SLSA-not-included header note
- `python-publish-pypi.yml`: replace unpinned `pip install safety bandit` block with
  `uv run pip-audit --strict` and bandit against `pyproject.toml`
- `python-docker.yml`: flip `enable-sbom` default to `true`; add `enable-provenance` input
  (default `true`)

#### Acceptance Criteria

- No `${{ inputs.* }}` appears unquoted in any `run:` shell block across all 23 workflows
- No `${{ inputs.* }}` interpolated directly as Python syntax inside any heredoc
- `synthetic-data-script` input does not exist in any workflow
- `python-release.yml` artifact upload step has `if: always()`
- Docker `enable-sbom` defaults `true`; `enable-provenance` input exists and defaults `true`
- All supply chain items updated (SLSA template SHA pins, pip-audit, Docker provenance)
- `workflow_dispatch` trigger confirmed on downstream test repo before PR marked ready

#### Quality Gates

- `qlty check` (actionlint + shellcheck) passes on all modified workflow YAML before each commit
- `pre-commit run --all-files` passes before each commit
- All inputs in `run:` blocks use env-var isolation pattern (zero direct interpolation)
- Migration notes present in headers of all workflows with breaking input changes

#### Estimated Duration

1 focused session (two parallel worktrees, merge, PR review)

---

### Phase 2: Architecture Cleanup

**Branch:** `fix/workflow-architecture-cleanup`
**Depends on:** Phase 1 merged to `main`
**Breaking:** yes; callers using `enable-sonarcloud`, `enable-codecov`, or
`python-pr-validation.yml` break on merge with no gradual migration window

#### Goal

Remove duplicated tooling, fix wrong org references, add the Scorecard score gate, and retire
`python-pr-validation.yml` with a hard-fail migration stub. All breaking changes documented
in workflow headers with migration notes.

#### Deliverables

- `python-ci.yml`: delete `sonarcloud-quality-gate` job (currently lines 579-636); remove
  `enable-sonarcloud`, `sonarcloud-organization`, `sonarcloud-project-key` inputs and
  `SONAR_TOKEN` secret; remove job from `ci-gate` `needs:` list; add migration header comment
  directing callers to `python-sonarcloud.yml`
- `python-ci.yml`: delete all 7 `codecov/codecov-action` steps and 3 test analytics steps;
  remove `enable-codecov` input and `CODECOV_TOKEN` secret; add migration header comment
  pointing callers to `python-codecov.yml`
- `python-ci.yml`: delete `check-secrets` job (gated only SonarCloud and Codecov, now gone);
  simplify `ci-gate` to check only `quality-checks`, `llm-governance`, `matrix-testing`
- `python-ci.yml`: add `-c pyproject.toml` to bandit invocation; replace safety with
  `uv run pip-audit --strict`
- `python-fuzzing.yml`, `python-performance-regression.yml`, `python-qlty-coverage.yml`: fix
  wrong org references from `williaby/.github/` to `ByronWilliamsCPA/.github/` (3 files,
  line 9 or 12 each)
- `python-scorecard.yml`: add `min-score` input (number, default 4); add score-gate step that
  parses SARIF and exits nonzero when any gated check (`Branch-Protection`, `Code-Review`,
  `Dangerous-Workflow`, `Token-Permissions`, `Pinned-Dependencies`) scores below threshold;
  all inputs read via `os.environ`
- `python-sonarcloud.yml`, `python-qlty-coverage.yml`: add `timeout-minutes: 5` to
  `check-configuration` job
- `python-compatibility.yml`: add `timeout-minutes: 5` to `build-matrix` and
  `compatibility-summary` jobs
- `python-pr-validation.yml`: replace all job content with single `migration-required` job
  that exits 1 and prints migration message directing callers to `python-ci.yml` and
  `python-supplemental-checks.yml`
- `python-supplemental-checks.yml`: replace PR-title string matching for Dependabot
  major/minor/patch classification with native Dependabot label check (`major`, `minor`,
  `patch` labels); not spoofable via PR title manipulation

Note: `python-codecov.yml` (the standalone reusable workflow) is retained. Only the inline
Codecov steps inside `python-ci.yml` are removed.

#### Acceptance Criteria

- `python-ci.yml` has no SonarCloud job, no Codecov steps, no `check-secrets` job
- `python-ci.yml` bandit invocation includes `-c pyproject.toml`
- All three wrong org references corrected (`williaby` replaced with `ByronWilliamsCPA`)
- `python-scorecard.yml` exits nonzero when any gated check scores below `min-score`
- `python-pr-validation.yml` exits 1 with migration message on every trigger
- All four missing `timeout-minutes` added
- `workflow_dispatch` trigger confirmed on downstream test repo before PR marked ready

#### Quality Gates

- `qlty check` (actionlint + shellcheck) passes on all modified workflow YAML before each commit
- `pre-commit run --all-files` passes before each commit
- Migration notes present in all headers for removed inputs and jobs
- No new `${{ inputs.* }}` direct interpolation introduced in any `run:` block

#### Estimated Duration

1 focused session (single worktree, no parallel work needed)

---

### Phase 3: New Capabilities

**Branch:** `feat/workflow-new-capabilities`
**Depends on:** Phase 2 merged to `main`
**Breaking:** no; additive only

#### Goal

Add `python-precommit.yml` and `python-standard-stack.yml` as new reusable workflows and wire
commit-lint into `python-supplemental-checks.yml`. All new workflows use the env-var isolation
pattern established in Phase 1.

#### Deliverables

- `python-precommit.yml` (new reusable `workflow_call` workflow): inputs `config-path`
  (string, default `.pre-commit-config.yaml`), `python-version` (string, default `3.12`),
  `show-diff-on-failure` (boolean, default `true`); steps: harden-runner (egress: audit), checkout,
  setup-uv, `uv sync`, `pre-commit run --all-files`; all inputs via env vars in `run:` blocks
- `python-standard-stack.yml` (new caller reusable workflow): chains `python-ci.yml`,
  `python-security-analysis.yml`, `python-sbom.yml` using `needs:`; documents itself as the
  recommended starting point for new repos; exposes `python-version` (string, default `3.12`),
  `source-directory` (string, default `src`), `coverage-threshold` (number, default `80`),
  `fail-on-high` (boolean, default `true`); optional secret passthroughs: `SONAR_TOKEN`,
  `CODECOV_TOKEN`; nesting depth is 2 levels (caller calls standard-stack which calls
  ci/security/sbom), within GitHub's 4-level reusable workflow limit
- `python-supplemental-checks.yml`: add optional `commit-lint` job gated on new boolean input
  `enable-commit-lint` (default `false`); uses `amannn/action-semantic-pull-request`
  (SHA-pinned) to validate PR title follows Conventional Commits format

#### Acceptance Criteria

- `python-precommit.yml` exists, is callable via `workflow_call`, and runs pre-commit hooks
  end-to-end against a test caller
- `python-standard-stack.yml` exists and chains CI + security + SBOM with minimal caller
  config (four inputs maximum for a new repo)
- `python-supplemental-checks.yml` has `enable-commit-lint` input wired to semantic PR title
  check via SHA-pinned `amannn/action-semantic-pull-request`
- `workflow_dispatch` trigger confirmed on downstream test repo before PR marked ready

#### Quality Gates

- `qlty check` (actionlint + shellcheck) passes on all new and modified workflow YAML before
  each commit
- `pre-commit run --all-files` passes before each commit
- All inputs in `run:` blocks use env-var isolation pattern (zero direct interpolation)
- All new action references SHA-pinned with version comment

#### Estimated Duration

1 focused session (single worktree, additive only)

---

## Cross-Cutting Requirements

These requirements apply to every phase and every commit.

| Requirement | Detail |
| --- | --- |
| Input isolation | All inputs used in `run:` blocks declared in `env:` and referenced as `$VAR` (shell) or `os.environ["VAR"]` (Python). No direct `${{ inputs.* }}` in `run:` blocks. |
| Pre-commit | `pre-commit run --all-files` before every commit |
| Workflow linting | `qlty check` (actionlint + shellcheck) on all modified workflow YAML before each commit |
| Worktree location | `.worktrees/<branch-slug>` inside the project root; never at global paths |
| Commit style | Conventional commits, signed commits |
| Migration notes | In-file migration comments in headers of all workflows with breaking changes |
| End-to-end validation | `workflow_dispatch` on downstream test repo before each PR is marked ready |
| Action pins | All action references SHA-pinned with version comment (e.g., `actions/checkout@<sha>  # v4.x.x`) |

---

## Risk Register

| Risk | Source | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- | --- |
| Merge conflict between Worktree A and Worktree B outputs | ADR-001 | Low | Medium | Worktree A scoped strictly to `python-performance-regression.yml` only; Worktree B touches no files in Worktree A scope |
| actionlint/shellcheck missed if `qlty check` not run locally | ADR-001 | Medium | High | Enforce `qlty check` as a quality gate before each commit; document in phase acceptance criteria |
| Callers break on Phase 2 merge with no gradual migration window | ADR-001 | High | Medium | Hard-fail job in `python-pr-validation.yml` provides immediate signal; migration notes in all removed-input headers |
| Docker `enable-sbom` default flip increases artifact storage costs for opt-out callers | ADR-001 | Low | Low | Document the flip in the workflow header; callers can add `enable-sbom: false` explicitly |
| `python-standard-stack.yml` nesting depth could approach GitHub's reusable workflow limit | Spec | Low | Medium | Nesting is 2 levels (caller to standard-stack to called workflows); GitHub limit is 4 levels; margin is sufficient |
| Scorecard SARIF schema differences across runner versions could break score-gate parsing | Spec | Low | Medium | Parse only known fields; add fallback that treats missing score as passing (fail-open on unknown schema) |
| Supply chain fixes (pip-audit, Docker provenance) may require caller-side `pyproject.toml` changes | Spec | Medium | Medium | Document pip-audit requirement in workflow headers; bandit `-c pyproject.toml` requires a `[tool.bandit]` section |

---

## Success Metrics

**Phase 1 complete when all of the following are true:**

- Zero instances of `${{ inputs.* }}` unquoted in any `run:` shell block across all 23 workflows
- Zero instances of `${{ inputs.* }}` interpolated directly as Python syntax in any heredoc
- `synthetic-data-script` input does not exist in any file
- `python-release.yml` artifact upload step has `if: always()`
- Docker `enable-sbom` defaults `true`; `enable-provenance` input exists
- `qlty check` and `pre-commit run --all-files` both pass on all modified files

**Phase 2 complete when all of the following are true:**

- `python-ci.yml` contains no SonarCloud job, no Codecov steps, no `check-secrets` job
- `python-ci.yml` bandit invocation passes `-c pyproject.toml`
- All three wrong org references corrected
- `python-scorecard.yml` exits nonzero when any gated check scores below `min-score`
- `python-pr-validation.yml` exits 1 with migration message on every trigger
- All four missing `timeout-minutes` added
- `qlty check` and `pre-commit run --all-files` both pass on all modified files

**Phase 3 complete when all of the following are true:**

- `python-precommit.yml` exists, is callable, and runs pre-commit hooks end-to-end
- `python-standard-stack.yml` exists and chains CI + security + SBOM with minimal config
- `python-supplemental-checks.yml` has `enable-commit-lint` input wired to semantic PR check
- `qlty check` and `pre-commit run --all-files` both pass on all new and modified files

---

## Phase 0 Checklist: Environment Setup

Before beginning Phase 1, verify the following:

- [ ] Confirm working directory is `/home/byron/dev/.github` (the org-level workflow repo)
- [ ] Run `git status` to confirm branch is clean and on the intended starting point
- [ ] Run `git pull origin main` to ensure `main` is current
- [ ] Verify `.worktrees/` is listed in `.gitignore` (`grep worktrees .gitignore`)
- [ ] Confirm `qlty check` is available and configured (`qlty check --version`)
- [ ] Confirm `pre-commit` is installed (`pre-commit --version`)
- [ ] Confirm a downstream test repo is accessible for `workflow_dispatch` validation
- [ ] Create Worktree A: `git worktree add .worktrees/fix-perf-regression-rce fix/perf-regression-rce`
- [ ] Create Worktree B: `git worktree add .worktrees/fix-workflow-input-quoting fix/workflow-input-quoting`
- [ ] Verify both worktrees appear in `git worktree list`
