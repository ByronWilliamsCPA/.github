# Workflow Security and Architecture Remediation Design

**Date:** 2026-04-30
**Status:** Approved
**Scope:** All 23 reusable workflows in `.github/workflows/`
**Source:** Comprehensive three-domain audit (security, architecture, supply chain) conducted 2026-04-29

---

## Background

A parallel agent audit of the 23 reusable org-level GitHub Actions workflows identified:

- 3 critical findings (one RCE vector, one code injection vector, one missing SLSA provenance)
- 6 high findings (permissions over-scoping, shell injection via unquoted inputs)
- Multiple medium findings (egress policy, artifact integrity, false-assurance security gates)
- Architecture gaps (duplicated tooling with divergent configs, wrong org references, missing workflows)
- Supply chain gaps (Docker SBOM/provenance off by default, pip-audit not used consistently)

---

## Delivery Structure

Three sequential PRs. Each depends on the previous merging to `main`.

| PR | Branch | Focus | Breaking |
|---|---|---|---|
| 1 | `fix/workflow-security-remediation` | Security fixes + supply chain | Soft (Docker SBOM/provenance defaults flip to `true`) |
| 2 | `fix/workflow-architecture-cleanup` | Architecture refactor | Yes |
| 3 | `feat/workflow-new-capabilities` | New workflows | No |

---

## PR 1: Security + Supply Chain

**Branch:** `fix/workflow-security-remediation`
**Implementation:** Two parallel worktrees merged into the branch before PR.

### Worktree A -- `fix/perf-regression-rce`

Touches only `python-performance-regression.yml`. Resolves CRIT-01 and CRIT-02.

**CRIT-01: Remove `synthetic-data-script` input (arbitrary Python RCE)**

The `synthetic-data-script` input accepted arbitrary Python code from callers and executed it verbatim inside a `python - <<'EOF'` heredoc. This is an RCE vector for any caller that enables `generate-synthetic-data: true`.

Remediation: Remove the input entirely. Replace the heredoc block with:

```yaml
- name: Generate synthetic test data
  env:
    GENERATE_DATA: ${{ inputs.generate-synthetic-data }}
  run: |
    if [ "$GENERATE_DATA" = "true" ]; then
      uv run python scripts/generate_test_data.py
    fi
```

Callers place their data-generation script at `scripts/generate_test_data.py` in their repo. Document this convention in the workflow header.

**CRIT-02: Move heredoc inputs to env vars**

All numeric and boolean inputs used inside `python - <<'EOF'` blocks interpolated as raw Python syntax. GitHub does not enforce declared input types, so callers can inject Python expressions.

Remediation pattern -- for every Python heredoc that references `${{ inputs.* }}`:

```yaml
env:
  PRIMARY_METRIC: ${{ inputs.primary-metric }}
  REGRESSION_THRESHOLD: ${{ inputs.regression-threshold }}
  IMPROVEMENT_THRESHOLD: ${{ inputs.improvement-threshold }}
  FAIL_ON_REGRESSION: ${{ inputs.fail-on-regression }}
run: |
  uv run python - <<'EOF'
  import os
  primary_metric = os.environ["PRIMARY_METRIC"]
  regression_threshold = float(os.environ["REGRESSION_THRESHOLD"])
  improvement_threshold = float(os.environ["IMPROVEMENT_THRESHOLD"])
  fail_on_regression = os.environ["FAIL_ON_REGRESSION"] == "true"
  ...
  EOF
```

Apply to every Python heredoc in the file that currently uses `${{ inputs.* }}` interpolation (lines 185-192, 348, 353-354, 419).

**HIGH-05: Benchmark inputs to env vars**

`benchmark-script`, `benchmark-args`, `warmup-iterations`, `benchmark-iterations` all interpolated unquoted into shell commands. Apply the same env-var pattern and quote all shell references:

```yaml
env:
  BENCHMARK_SCRIPT: ${{ inputs.benchmark-script }}
  BENCHMARK_ARGS: ${{ inputs.benchmark-args }}
run: |
  uv run python "$BENCHMARK_SCRIPT" $BENCHMARK_ARGS
```

### Worktree B -- `fix/workflow-input-quoting`

Systematic env-var pattern sweep across ~12 other files, plus supply chain fixes. All string inputs used in `run:` blocks must be declared in an `env:` block and referenced with `"$VAR"` quoting.

**Files and specific inputs to fix:**

`python-ci.yml`:
- `source-directory`, `test-directory` in ruff, basedpyright, vulture, pytest, bandit steps
- `python-version` in uv python install step
- `dead-code-confidence` in vulture step (numeric -- pass via env, parse as integer in shell)
- Permissions: move `pull-requests: write` and `checks: write` from workflow level to job level (only on jobs that actually need them -- none do after Codecov removal lands in PR 2; remove both from workflow level now, add back only if a specific job requires it)
- Fix `|| true` swallowing in integration and security test steps: replace with exit-code-5 check pattern:

```bash
uv run pytest -m "integration" ... ; EXIT=$?
if [ $EXIT -ne 0 ] && [ $EXIT -ne 5 ]; then exit $EXIT; fi
```

`python-compatibility.yml`:
- `operating-systems`, `python-versions` in matrix build step
- `system-deps-ubuntu`, `system-deps-macos`, `system-deps-windows` in system package install steps
- Add pattern validation before sudo install:

```bash
PKGS="$SYSTEM_DEPS_UBUNTU"
if [[ "$PKGS" =~ ^[a-zA-Z0-9_\-\. ]+$ ]]; then
  sudo apt-get install -y $PKGS
else
  echo "::error::Invalid package name characters in system-deps-ubuntu"; exit 1
fi
```

`python-docs.yml`:
- Move `id-token: write` from workflow level to `deploy` job level only
- Add harden-runner as first step in `deploy` job with `egress-policy: block` and `allowed-endpoints: api.github.com:443`
- Remove redundant `actions/cache` step (uv's built-in cache via setup-uv is sufficient)

`python-release.yml`:
- Move `id-token: write`, `attestations: write`, `contents: write`, `pull-requests: write` from workflow level to the specific jobs that need them (`release` job: contents/write, id-token/write, attestations/write; `publish-pypi` job: id-token/write)
- Remove `issues: write` from workflow level (no job uses it)
- Set workflow-level permissions to `contents: read`
- Add `if: always()` to the artifact upload step (line 267)

`python-security-analysis.yml`:
- Move boolean inputs `fail-on-high`, `fail-on-medium` in Python heredoc to env vars and read via `os.environ`

`python-pr-validation.yml`:
- Apply env-var pattern to remaining string inputs used in `run:` blocks

**Supply chain fixes (also in Worktree B):**

`python-slsa.yml`:
- Replace `actions/checkout@v4` in comment examples with `actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd  # v6.0.2`
- Replace `actions/upload-artifact@v4` in comment examples with `actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a  # v7.0.1`
- Add prominent note in header: "SLSA provenance is NOT included in `python-release.yml`. Every caller must add the provenance job from this template to their own top-level release workflow."

`python-publish-pypi.yml`:
- Remove the pre-publish security check block that uses `pip install safety bandit` (unpinned) with `|| echo` error suppression
- Replace with:

```yaml
- name: Pre-publish security checks
  env:
    SRC_DIR: ${{ inputs.source-directory }}
  run: |
    uv run pip-audit --strict
    uv run bandit -r "$SRC_DIR" -c pyproject.toml -ll
```

`python-docker.yml`:
- Change `enable-sbom` default from `false` to `true`
- Add new `enable-provenance` input (boolean, default: `true`) separate from `enable-sbom`
- Update `docker/build-push-action` step:

```yaml
sbom: ${{ inputs.enable-sbom }}
provenance: ${{ inputs.enable-provenance }}
```

### PR 1 Merge Sequence

1. Worktree A merges into `fix/workflow-security-remediation` first (smaller, easier to review)
2. Worktree B merges into `fix/workflow-security-remediation` (resolve any conflicts)
3. Single PR from `fix/workflow-security-remediation` to `main`

---

## PR 2: Architecture Cleanup

**Branch:** `fix/workflow-architecture-cleanup`
**Depends on:** PR 1 merged to `main`
**Implementation:** Single worktree

All breaking changes are documented with migration notes in the affected workflow headers.

### Remove SonarCloud from `python-ci.yml`

Delete the entire `sonarcloud-quality-gate` job (currently lines 579-636). Remove the `enable-sonarcloud`, `sonarcloud-organization`, `sonarcloud-project-key` inputs. Remove the `SONAR_TOKEN` secret declaration. Remove `sonarcloud-quality-gate` from the `ci-gate` job's `needs:` list and result check.

Update the workflow header:

```yaml
# MIGRATION: SonarCloud integration removed from this workflow.
# Callers using enable-sonarcloud must switch to calling
# python-sonarcloud.yml as a separate job:
#
#   jobs:
#     ci:
#       uses: ByronWilliamsCPA/.github/.github/workflows/python-ci.yml@main
#     sonarcloud:
#       needs: ci
#       uses: ByronWilliamsCPA/.github/.github/workflows/python-sonarcloud.yml@main
#       with:
#         sonar-organization: 'your-org'
#         sonar-project-key: 'your-key'
#       secrets:
#         SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
```

### Remove inline Codecov from `python-ci.yml`

Delete all 7 `codecov/codecov-action` steps and the 3 test analytics steps from the `quality-checks` job. Remove `enable-codecov` input. Remove `CODECOV_TOKEN` secret declaration.

Update the workflow header with migration note pointing callers to `python-codecov.yml`.

### Remove `check-secrets` job from `python-ci.yml`

The `check-secrets` job existed solely to gate the SonarCloud and Codecov optional jobs. With both removed, it serves no purpose. Delete the job and remove it from `ci-gate`'s `needs:` list. The `ci-gate` simplifies to checking only `quality-checks`, `llm-governance`, and `matrix-testing`.

### Align bandit configuration in `python-ci.yml`

Add `-c pyproject.toml` to the bandit invocation in `quality-checks`. Replace `uv pip compile pyproject.toml -o requirements.txt && safety check -r requirements.txt` with `uv run pip-audit --strict` (consistent with `python-publish-pypi.yml` after PR 1).

### Fix wrong org references

Three usage comment examples reference `williaby/.github/` instead of `ByronWilliamsCPA/.github/`:
- `python-fuzzing.yml` line 9
- `python-performance-regression.yml` line 9
- `python-qlty-coverage.yml` line 12

Simple find-and-replace in each file.

### Add Scorecard score gate to `python-scorecard.yml`

Add input:
```yaml
min-score:
  description: 'Minimum acceptable score per check (0-10). Checks below this threshold fail the workflow.'
  type: number
  required: false
  default: 4
```

Add step after SARIF upload:

```yaml
- name: Evaluate Scorecard Scores
  env:
    MIN_SCORE: ${{ inputs.min-score }}
  run: |
    python3 - <<'EOF'
    import json, os, sys

    with open('scorecard-results.sarif') as f:
        sarif = json.load(f)

    min_score = float(os.environ["MIN_SCORE"])
    gate_checks = {"Branch-Protection", "Code-Review", "Dangerous-Workflow",
                   "Token-Permissions", "Pinned-Dependencies"}
    failures = []

    for run in sarif.get("runs", []):
        for result in run.get("results", []):
            rule_id = result.get("ruleId", "")
            score = result.get("properties", {}).get("score", 10)
            if rule_id in gate_checks and score < min_score:
                failures.append(f"{rule_id}: {score}/10 (minimum {min_score})")

    if failures:
        print("::error::Scorecard score gate failed:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print(f"Scorecard score gate passed (all gated checks >= {min_score}/10)")
    EOF
```

Note: inputs used inside this heredoc are read via `os.environ` (consistent with the env-var pattern established in PR 1).

### Add missing `timeout-minutes`

- `check-configuration` in `python-sonarcloud.yml`: 5 minutes
- `check-configuration` in `python-qlty-coverage.yml`: 5 minutes
- `build-matrix` in `python-compatibility.yml`: 5 minutes
- `compatibility-summary` in `python-compatibility.yml`: 5 minutes

### Hard-fail `python-pr-validation.yml`

Replace all job content with a single failing job that directs callers to migrate:

```yaml
jobs:
  migration-required:
    name: This workflow is removed
    runs-on: ubuntu-latest
    steps:
      - name: Migration required
        run: |
          echo "::error::python-pr-validation.yml has been removed."
          echo "::error::Migrate to python-ci.yml and python-supplemental-checks.yml."
          echo "::error::See .github/workflows/python-ci.yml header for usage."
          exit 1
```

### Fix `python-supplemental-checks.yml` auto-merge detection

Replace PR-title string matching for major/minor/patch classification with Dependabot's native label approach. Check for labels `major`, `minor`, `patch` set by Dependabot instead of parsing the PR title string. This is not spoofable via PR title manipulation.

---

## PR 3: New Capabilities

**Branch:** `feat/workflow-new-capabilities`
**Depends on:** PR 2 merged to `main`
**Implementation:** Single worktree, additive only

### `python-precommit.yml` (new workflow)

Reusable `workflow_call` workflow following the same structure as all existing workflows.

Inputs:
- `config-path`: string, default `.pre-commit-config.yaml`
- `python-version`: string, default `3.12`
- `fail-fast`: boolean, default `true`

Steps: harden-runner (egress: audit), checkout, setup-uv, uv sync, run pre-commit.

All inputs passed via env vars in `run:` blocks.

### `python-standard-stack.yml` (new composite entry point)

A "quickstart" `workflow_call` workflow that chains `python-ci.yml`, `python-security-analysis.yml`, and `python-sbom.yml` using `needs:`. Documents itself as the recommended starting point for new repos.

Exposes only the most common inputs:
- `python-version` (string, default `3.12`)
- `source-directory` (string, default `src`)
- `coverage-threshold` (number, default `80`)
- `fail-on-high` (boolean, default `true`)

Optional secret passthroughs: `SONAR_TOKEN`, `CODECOV_TOKEN`.

### Commit linting in `python-supplemental-checks.yml`

Add optional job `commit-lint` gated on new boolean input `enable-commit-lint` (default: `false`).

Uses `amannn/action-semantic-pull-request` (SHA-pinned) to validate PR title follows Conventional Commits format. Individual commit message validation (via `commitlint`) is out of scope: it requires a `commitlint.config.js` in every caller repo and is better enforced by pre-commit hooks (which `python-precommit.yml` covers).

---

## What This Does Not Include

- Egress policy upgrades (`audit` to `block`) across all 23 workflows -- high effort, requires endpoint discovery per job, deferred to a standalone "harden egress" spike.
- Mid-job `git checkout origin/main` refactor in `python-performance-regression.yml` (MED-07) -- requires splitting the comparison into separate jobs, significant redesign, deferred.
- SBOM attachment to GitHub Releases from `python-sbom.yml` -- requires `python-release.yml` coordination, deferred.
- `python-codecov.yml` `CODECOV_TOKEN: required: true` → `required: false` -- low priority, deferred to PR 3 or standalone.
- MED-06 (`check-secrets` boolean exposure) -- removed entirely by PR 2 cleanup, resolves itself.

---

## Success Criteria

**PR 1 complete when:**
- No `${{ inputs.* }}` appears unquoted in any `run:` shell block across all 23 workflows
- No `${{ inputs.* }}` appears interpolated directly as Python syntax inside any heredoc
- `synthetic-data-script` input does not exist
- All supply chain items (SLSA template, pip-audit, Docker provenance defaults) are updated
- `python-release.yml` artifact upload step has `if: always()`

**PR 2 complete when:**
- `python-ci.yml` contains no SonarCloud job, no Codecov steps, no `check-secrets` job
- Bandit invocation in `python-ci.yml` passes `-c pyproject.toml`
- All three wrong org references corrected
- `python-scorecard.yml` exits nonzero when gated checks score below `min-score`
- `python-pr-validation.yml` exits 1 with migration message on every trigger
- All missing `timeout-minutes` added

**PR 3 complete when:**
- `python-precommit.yml` exists, is callable, runs pre-commit hooks end-to-end
- `python-standard-stack.yml` exists and chains CI + security + SBOM with minimal caller config
- `python-supplemental-checks.yml` has `enable-commit-lint` input wired to semantic PR title check
