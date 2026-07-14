# python-security-analysis.yml -- Reusable security analysis workflow

## Quick Reference

**Workflow**: `.github/workflows/python-security-analysis.yml`
**Type**: Reusable (`workflow_call`)
**Security**: CodeQL, Bandit, OSV-Scanner, and Dependency Review, each independently
toggleable; CodeQL uploads SARIF to code scanning

## Purpose

`python-security-analysis.yml` runs a bundle of four independent security scanners against
a caller repository: CodeQL static analysis, Bandit SAST, OSV-Scanner dependency
vulnerability scanning, and (on pull requests) GitHub's Dependency Review action. Each
scanner is gated behind its own boolean input, so callers can disable any scanner that
duplicates a tool they already run elsewhere.

CodeQL and Bandit additionally only run when a `detect-changes` path filter finds a Python
source file, workflow file, or dependency manifest changed in the diff, so unrelated pushes
do not burn CI minutes on a full scan. A final `security-gate` job aggregates the result of
every scanner job (treating `skipped` as acceptable) and fails the run if any enabled
scanner failed.

## When to use this workflow

Use `python-security-analysis.yml` for any Python repository that manages dependencies with
`uv` (a `pyproject.toml`, ideally with a committed `uv.lock`) and wants CodeQL, Bandit, and
OSV-Scanner coverage without hand-rolling each tool separately.

## When NOT to use it

- **Poetry repositories are not supported.** The `codeql` and `python-security` jobs detect
  a `poetry.lock` or a `[tool.poetry]` table in `pyproject.toml` and fail fast with an
  actionable `::error::` message rather than attempting to scan. Convert the repo to `uv`
  first.
- Repositories with no `pyproject.toml` at the repo root skip CodeQL and Bandit with a
  step-summary notice (not a failure); remove the caller entirely if the repo does not need
  Python security scanning.
- If your workflow already runs an equivalent scanner (Safety, Trivy, Snyk, etc.), disable
  the redundant input rather than running both. Note that the `run-safety` input is a
  deprecated no-op (see Inputs below); it does not control anything.

## Minimal usage

```yaml
name: Security Analysis

on:
  pull_request:
  schedule:
    - cron: '0 6 * * 1'

jobs:
  security:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-security-analysis.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    permissions:
      contents: read
      security-events: write  # codeql job (SARIF upload)
      actions: read           # codeql job
      pull-requests: write    # dependency-review job (PR comment summary)
    with:
      source-directory: 'src'
      fail-on-high: true
    secrets: inherit
```

## Inputs

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| `source-directory` | string | `src` | Source code directory to scan |
| `python-version` | string | `3.12` | Python version for scanning |
| `fail-on-high` | boolean | `true` | Fail the build on HIGH/CRITICAL vulnerabilities (OSV-Scanner) |
| `fail-on-medium` | boolean | `false` | Fail the build on MEDIUM vulnerabilities (OSV-Scanner) |
| `run-codeql` | boolean | `true` | Run CodeQL analysis |
| `run-dependency-review` | boolean | `true` | Run Dependency Review (pull requests only) |
| `run-bandit` | boolean | `true` | Run Bandit static analysis |
| `run-osv` | boolean | `true` | Run OSV Scanner |
| `no-build` | boolean | `true` | Pass `--no-build` to `uv sync`/`uv run`; disable for projects using a build backend such as hatchling |
| `run-safety` | boolean | `false` | Deprecated no-op. The Safety scanner was removed in PR #140; this input is kept only so pre-#140 callers do not startup-fail. No job reads it; remove it from your `with:` block |

## Outputs

None.

## Required Permissions

SARIF upload (CodeQL) and the Dependency Review PR comment summary both need scopes beyond
the read-only default, so the caller must grant them explicitly:

```yaml
permissions:
  contents: read
  security-events: write  # codeql job: upload SARIF results to code scanning
  actions: read            # codeql job: required by github/codeql-action
  pull-requests: write     # dependency-review job: post PR comment summary
```

Grant these at the calling job level (tighter, and preferred when the caller workflow has
other jobs that need narrower grants) or at the workflow level. GitHub validates a called
job's permission requests against the caller's grant at workflow parse/startup time: a
called job that requests a scope the caller did not grant fails the entire run at startup
(`startup_failure`), before any job executes, not just the job that needed the extra scope.

If you disable `run-codeql` and rely on a separate `codeql.yml`, you may omit `actions:
read` and `security-events: write`. If you disable `run-dependency-review`, you may omit
`pull-requests: write`. When in doubt, grant all four.

## Troubleshooting

### Run fails with `startup_failure` before any job starts

**Symptoms**:

```text
This run likely failed due to a workflow file issue.
```

**Solutions**:

1. Confirm the caller's `permissions:` block grants all four scopes shown in
   [Required Permissions](#required-permissions).
2. If you intentionally disabled a scanner (`run-codeql: false` or
   `run-dependency-review: false`), you may narrow the grant accordingly; otherwise grant
   all four.
3. Verify with:

   ```bash
   gh run list -R ByronWilliamsCPA/<repo> --workflow=security-analysis.yml
   gh run view <run-id> --json conclusion
   ```

   A `startup_failure` conclusion means the grant is still insufficient; any run that starts
   confirms the grant passed validation.

### CodeQL scan runs but no code scanning alerts appear

**Symptoms**: the `codeql` job succeeds, but no SARIF results show up under the repository's
Security > Code scanning alerts tab.

**Solutions**:

1. Confirm the caller granted both `security-events: write` and `actions: read`; the
   `github/codeql-action/analyze` step needs both to upload results even though the scan
   itself can complete without them.
2. If the repository is private, confirm GitHub Advanced Security is enabled; without it,
   code scanning is unavailable regardless of workflow permissions.

### CodeQL and Bandit jobs report `skipped` on every run

**Symptoms**: the `codeql` and `python-security` jobs consistently show `skipped`, and
`security-gate` still passes.

**Solutions**:

1. This is expected when the diff does not touch any of the paths the `detect-changes`
   filter watches: `**/*.py`, `.github/workflows/**`, `pyproject.toml`, `poetry.lock`,
   `uv.lock`, or `requirements*.txt`. A PR that only touches docs or non-Python config
   legitimately skips both, and `security-gate` treats `skipped` as passing.
2. If you need scans to run unconditionally, this workflow does not currently expose an
   override for the path filter; rely on the scheduled run (as in the minimal usage example)
   for periodic full coverage instead.

### Job fails with "This repo uses Poetry"

**Symptoms**:

```text
Error: This repo uses Poetry. The python-security-analysis.yml reusable workflow is
uv-only by org policy. Convert this repo to uv before re-enabling Python security analysis.
```

**Solutions**:

1. Convert the repository to `uv` (remove `poetry.lock`, migrate `pyproject.toml` off
   `[tool.poetry]`) before re-enabling `python-security-analysis.yml`.

## Additional Resources

- [CodeQL documentation](https://codeql.github.com/docs/)
- [Bandit documentation](https://bandit.readthedocs.io/)
- [OSV-Scanner documentation](https://google.github.io/osv-scanner/)
- [Dependency Review Action](https://github.com/actions/dependency-review-action)
