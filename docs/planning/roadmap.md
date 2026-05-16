# Workflow Security and Architecture Remediation Roadmap

**TL;DR:** Three sequential PRs over three implementation sessions. Phase 1 resolves all critical and high security findings. Phase 2 applies breaking architecture cleanup. Phase 3 adds new capabilities. Each phase gates on the previous merging to `main`.

**Source:** `docs/superpowers/specs/2026-04-30-workflow-security-architecture-remediation-design.md`
**ADR:** `docs/planning/adr/adr-001-workflow-security-remediation-delivery.md`

---

## Phase 1: Security Fixes and Supply Chain

**Branch:** `fix/workflow-security-remediation`
**Gate:** Merges to `main` before Phase 2 branches

### Phase 1 Deliverables

**Worktree A** (`fix/perf-regression-rce` at `.worktrees/fix-perf-regression-rce`):

- Remove `synthetic-data-script` input from `python-performance-regression.yml` (CRIT-01 RCE)
- Move all Python heredoc inputs to `env:` blocks, read via `os.environ` (CRIT-02)
- Move `benchmark-script`, `benchmark-args`, `warmup-iterations`, `benchmark-iterations` to env vars (HIGH-05)

**Worktree B** (`fix/workflow-input-quoting` at `.worktrees/fix-workflow-input-quoting`):

- `python-ci.yml`: env-var pattern for all string inputs; move workflow-level permissions to job level; fix `|| true` swallowing with exit-code-5 pattern (see spec for shell snippet)
- `python-compatibility.yml`: env-var pattern; pattern-validate package names before sudo install
- `python-docs.yml`: move `id-token: write` to deploy job; add harden-runner to deploy job; remove redundant cache step
- `python-release.yml`: move all permissions to job level; remove `issues: write`; add `if: always()` to artifact upload
- `python-security-analysis.yml`: move boolean heredoc inputs to env vars
- `python-pr-validation.yml`: env-var pattern for remaining string inputs (note: Phase 2 replaces this workflow's entire job content; Phase 1 only hardens the existing inputs)
- `python-slsa.yml`: SHA-pin comment examples; add SLSA-not-included header note
- `python-publish-pypi.yml`: replace unpinned safety block with `uv run pip-audit --strict` + bandit (pip-audit also added to `python-ci.yml` in Phase 2)
- `python-docker.yml`: flip `enable-sbom` default to `true`; add `enable-provenance` input (default `true`)

### Phase 1 Success Criteria

- No `${{ inputs.* }}` unquoted in any `run:` shell block across all 23 workflows
- No `${{ inputs.* }}` interpolated directly as Python syntax in any heredoc
- `synthetic-data-script` input removed
- `python-release.yml` artifact upload has `if: always()`
- Docker `enable-sbom` defaults `true`, `enable-provenance` input exists
- `qlty check` (actionlint + shellcheck) passes on all modified files
- `pre-commit run --all-files` passes before commit

### Phase 1 Duration

1 focused session (two parallel worktrees, merge, PR review)

---

## Phase 2: Architecture Cleanup

**Branch:** `fix/workflow-architecture-cleanup`
**Gate:** Requires Phase 1 merged to `main`

### Phase 2 Deliverables

- `python-ci.yml`: delete `sonarcloud-quality-gate` job (lines 579-636), all Codecov steps (7 action steps + 3 analytics), `check-secrets` job; add migration header comments; add `-c pyproject.toml` to bandit; replace safety with `uv run pip-audit --strict`
- `python-fuzzing.yml`, `python-performance-regression.yml`, `python-qlty-coverage.yml`: fix wrong org references (`williaby` to `ByronWilliamsCPA`)
- `python-scorecard.yml`: add `min-score` input (default 4); add score-gate step that parses SARIF and exits nonzero when gated checks score below threshold (see spec for exact Python snippet)
- `python-sonarcloud.yml`, `python-qlty-coverage.yml`: add `timeout-minutes: 5` to `check-configuration` job
- `python-compatibility.yml`: add `timeout-minutes: 5` to `build-matrix` and `compatibility-summary` jobs
- `python-pr-validation.yml`: replace all job content with single hard-fail job (exits 1, prints migration message to ci/supplemental-checks)
- `python-supplemental-checks.yml`: replace PR-title string matching with Dependabot native label check for auto-merge classification

Note: `python-codecov.yml` (the standalone reusable workflow) is retained. Only the inline Codecov steps inside `python-ci.yml` are removed. Callers migrate by calling `python-codecov.yml` directly.

### Phase 2 Success Criteria

- `python-ci.yml` has no SonarCloud job, no Codecov steps, no `check-secrets` job
- `python-ci.yml` bandit invocation includes `-c pyproject.toml`
- All three wrong org references corrected
- `python-scorecard.yml` exits nonzero when gated checks score below `min-score`
- `python-pr-validation.yml` exits 1 with migration message on every trigger
- All missing `timeout-minutes` added
- `qlty check` passes on all modified files
- `pre-commit run --all-files` passes before commit

### Phase 2 Duration

1 focused session (single worktree, no parallel work needed)

---

## Phase 3: New Capabilities

**Branch:** `feat/workflow-new-capabilities`
**Gate:** Requires Phase 2 merged to `main`

### Phase 3 Deliverables

- `python-precommit.yml` (new): reusable workflow with harden-runner, checkout, setup-uv, `uv sync`, pre-commit run; inputs `config-path`, `python-version`, `show-diff-on-failure` -- all via env vars
- `python-standard-stack.yml` (new): caller reusable workflow (`workflow_call` trigger) chaining `python-ci.yml`, `python-security-analysis.yml`, `python-sbom.yml` as called workflows via `needs:`; exposes `python-version`, `source-directory`, `coverage-threshold`, `fail-on-high`. Nesting depth: downstream caller calls standard-stack (level 1) which calls ci/security/sbom (level 2) -- within GitHub's 4-level reusable workflow limit.
- `python-supplemental-checks.yml`: add optional `commit-lint` job gated on `enable-commit-lint` input (default `false`); uses `amannn/action-semantic-pull-request` (SHA-pinned)

### Phase 3 Success Criteria

- `python-precommit.yml` exists, is callable, runs pre-commit hooks end-to-end
- `python-standard-stack.yml` exists and chains CI + security + SBOM with minimal caller config
- `python-supplemental-checks.yml` has `enable-commit-lint` input wired to semantic PR title check
- `qlty check` passes on all new and modified files
- `pre-commit run --all-files` passes before commit

### Phase 3 Duration

1 focused session (single worktree, additive only)

---

## Deferred (Out of Scope)

| Item | Reason |
| --- | --- |
| Egress policy upgrades (`audit` to `block`) across all 23 workflows | High effort, requires per-job endpoint discovery |
| Mid-job `git checkout origin/main` refactor in `python-performance-regression.yml` (MED-07) | Requires significant job-splitting redesign |
| SBOM attachment to GitHub Releases from `python-sbom.yml` | Requires `python-release.yml` coordination |
| `python-codecov.yml` `CODECOV_TOKEN: required: true` to `required: false` | Low priority |

---

## Cross-Cutting Requirements (All Phases)

- All inputs used in `run:` blocks declared in `env:` and referenced as `$VAR` or `os.environ["VAR"]`
- `qlty check` (actionlint + shellcheck) on all modified workflow YAML before each commit
- `pre-commit run --all-files` before each commit
- Worktrees created at `.worktrees/<branch-slug>` inside the project root
- Conventional commits, signed commits
- Migration notes in affected workflow headers for all breaking changes
- Validation: trigger modified workflows via `workflow_dispatch` on a downstream test repo to confirm end-to-end behavior before each PR is marked ready
