# python-security-analysis.yml -- Reusable security analysis workflow

## Quick Reference

**Workflow**: `.github/workflows/python-security-analysis.yml`
**Type**: Reusable (`workflow_call`)
**Security**: Bandit and OSV-Scanner, each independently toggleable

## Purpose

`python-security-analysis.yml` runs a bundle of two independent security scanners against
a caller repository: Bandit SAST and OSV-Scanner dependency vulnerability scanning. Each
scanner is gated behind its own boolean input, so callers can disable any scanner that
duplicates a tool they already run elsewhere.

A `detect-changes` path filter runs first, so unrelated pushes do not burn CI minutes on a
full scan. A final `security-gate` job aggregates the result of every scanner job (treating
`skipped` as acceptable) and fails the run if any enabled scanner failed.

CodeQL static analysis and GitHub's Dependency Review action were removed from this
workflow. Both require GitHub Advanced Security (Code Security), which GitHub now bills
separately, so neither functioned any longer. The `run-codeql` and `run-dependency-review`
inputs are still declared as inert no-ops; see [Inputs](#inputs).

## When to use this workflow

Use `python-security-analysis.yml` for any Python repository that manages dependencies with
`uv` (a `pyproject.toml`, ideally with a committed `uv.lock`) and wants Bandit and
OSV-Scanner coverage without hand-rolling each tool separately.

## When NOT to use it

- **Poetry repositories are not supported.** The `python-security` job detects a
  `poetry.lock` or a `[tool.poetry]` table in `pyproject.toml` and fails fast with an
  actionable `::error::` message rather than attempting to scan. Convert the repo to `uv`
  first.
- Repositories with no `pyproject.toml` at the repo root skip Bandit with a step-summary
  notice (not a failure); remove the caller entirely if the repo does not need Python
  security scanning.
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
      pull-requests: read     # detect-changes path filter
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
| `run-codeql` | boolean | `false` | Deprecated no-op. The CodeQL job was removed because it requires GitHub Advanced Security, which is now billed. No job reads it; remove it from your `with:` block |
| `run-dependency-review` | boolean | `false` | Deprecated no-op. The Dependency Review job was removed for the same reason. No job reads it; remove it from your `with:` block |
| `run-bandit` | boolean | `true` | Run Bandit static analysis |
| `run-osv` | boolean | `true` | Run OSV Scanner |
| `no-build` | boolean | `true` | Pass `--no-build` to `uv sync`/`uv run`; disable for projects using a build backend such as hatchling |
| `run-safety` | boolean | `false` | Deprecated no-op. The Safety scanner was removed in PR #140; this input is kept only so pre-#140 callers do not startup-fail. No job reads it; remove it from your `with:` block |

## Outputs

None.

## Required Permissions

The `detect-changes` path filter reads pull request metadata, so the caller must grant
`pull-requests: read` alongside `contents: read`:

```yaml
permissions:
  contents: read
  pull-requests: read      # detect-changes job: dorny/paths-filter
```

Grant these at the calling job level (tighter, and preferred when the caller workflow has
other jobs that need narrower grants) or at the workflow level. GitHub validates a called
job's permission requests against the caller's grant at workflow parse/startup time: a
called job that requests a scope the caller did not grant fails the entire run at startup
(`startup_failure`), before any job executes, not just the job that needed the extra scope.

No job requests `security-events: write`, `actions: read`, or `pull-requests: write` any
more; those were needed only by the removed CodeQL and Dependency Review jobs. Callers that
still grant them keep working, because over-granting is not a startup failure, but the grant
should be trimmed to the two scopes above. Do not narrow below `contents: read` plus
`pull-requests: read`.

## Troubleshooting

### Run fails with `startup_failure` before any job starts

**Symptoms**:

```text
This run likely failed due to a workflow file issue.
```

**Solutions**:

1. Confirm the caller's `permissions:` block grants both scopes shown in
   [Required Permissions](#required-permissions).
2. If the caller is still pinned to a SHA from before the CodeQL and Dependency Review jobs
   were deleted, that older callee still requests `security-events: write`, `actions: read`,
   and `pull-requests: write`. Either keep granting those four scopes or bump the pin first.
3. Verify with:

   ```bash
   gh run list -R ByronWilliamsCPA/<repo> --workflow=security-analysis.yml
   gh run view <run-id> --json conclusion
   ```

   A `startup_failure` conclusion means the grant is still insufficient; any run that starts
   confirms the grant passed validation.

### Bandit job reports `skipped` on every run

**Symptoms**: the `python-security` job consistently shows `skipped`, and `security-gate`
still passes.

**Solutions**:

1. This is expected when the diff does not touch any of the paths the `detect-changes`
   filter watches: `**/*.py`, `.github/workflows/**`, `pyproject.toml`, `poetry.lock`,
   `uv.lock`, or `requirements*.txt`. A PR that only touches docs or non-Python config
   legitimately skips it, and `security-gate` treats `skipped` as passing.
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

- [Bandit documentation](https://bandit.readthedocs.io/)
- [OSV-Scanner documentation](https://google.github.io/osv-scanner/)
