# python-release.yml -- Reusable release workflow

## Quick Reference

**Workflow**: `.github/workflows/python-release.yml`
**Type**: Reusable (`workflow_call`)
**Security**: Sigstore keyless signing (OIDC), SHA-256 artifact hashing, optional CycloneDX
SBOM generation, PyPI OIDC Trusted Publishing

## Purpose

`python-release.yml` builds a Python package, optionally runs a pre-release test gate,
versions and tags the release (either automatically via `python-semantic-release` or from a
manually pushed `v*` tag), signs the built artifacts with Sigstore, generates a CycloneDX
SBOM, records SHA-256 hashes of every artifact, creates the GitHub release, and optionally
publishes to PyPI using OIDC Trusted Publishing.

It can be triggered directly from a tag push or chained from an upstream CI workflow via
`workflow_run`; when triggered by `workflow_run`, the release job first verifies that the
triggering run originated from the same repository owner rather than a fork, before doing
anything else.

## When to use this workflow

Use `python-release.yml` for any `uv`-managed Python package repository that wants signed,
versioned GitHub releases, with or without PyPI publishing.

## When NOT to use it

- **Poetry repositories are not supported.** The `release` job detects a `poetry.lock` or a
  `[tool.poetry]` table in `pyproject.toml` and fails fast with an actionable error. Convert
  the repo to `uv` first.
- Repositories with no `pyproject.toml` fail the `release` job outright (unlike
  `python-ci.yml` or `python-security-analysis.yml`, which skip gracefully instead); a
  release workflow with nothing to build is treated as a caller misconfiguration, not a
  no-op.
- If you set `run-tests: false`, you must also supply a non-empty `skip-tests-reason`; the
  workflow fails fast otherwise, to prevent an accidental bypass of the pre-release quality
  gate.

## Minimal usage

```yaml
name: Release

on:
  push:
    tags: ['v*']

jobs:
  release:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-release.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    with:
      python-version: '3.12'
      semantic-release: true
      publish-to-pypi: false
    permissions:
      contents: write
      id-token: write
      attestations: write
      issues: write
      pull-requests: write
    secrets: inherit
```

## Inputs

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| `python-version` | string | `3.12` | Python version to use |
| `coverage-threshold` | number | `80` | Minimum code coverage percentage for pre-release tests |
| `source-directory` | string | `src` | Source code directory |
| `semantic-release` | boolean | `true` | Use `python-semantic-release` (`true`) or manual tag-based release (`false`) |
| `force-release` | string | `''` | Force a specific release type (empty for auto-detection) |
| `publish-to-pypi` | boolean | `false` | Publish to PyPI after the release is created |
| `pypi-package-name` | string | `''` | PyPI package name (used in the publish environment URL and step summary) |
| `pypi-url` | string | `https://upload.pypi.org/legacy/` | PyPI upload URL (override for a private index) |
| `run-tests` | boolean | `true` | Run the pre-release test gate (pytest with coverage, basedpyright, ruff) |
| `skip-tests-reason` | string | `''` | Reason for skipping pre-release tests. **Required** (non-empty) when `run-tests: false`; the job fails fast otherwise |
| `generate-sbom` | boolean | `true` | Generate a CycloneDX Software Bill of Materials |
| `sign-artifacts` | boolean | `true` | Sign build artifacts with Sigstore |
| `no-build` | boolean | `true` | Pass `--no-build` to `uv sync`/`uv run`; disable for projects using a build backend such as hatchling |

## Outputs

| Output | Description |
|--------|-------------|
| `released` | Whether a release was created (`'true'`/`'false'`) |
| `version` | The released version |
| `tag` | The release tag |

## Required Permissions

```yaml
permissions:
  contents: write      # push the release tag, create the GitHub release
  id-token: write       # OIDC token for Sigstore signing and PyPI trusted publishing
  attestations: write   # reserved for GitHub build-provenance attestation (see note below)
  issues: write         # python-semantic-release references issues in release notes
  pull-requests: write  # python-semantic-release references merged PRs in release notes
```

All five scopes are declared on the `release` job itself, so GitHub validates the caller's
grant against all five at startup, not just the three scopes shown in some older usage
examples. **Omitting `issues: write` or `pull-requests: write` produces a `startup_failure`
even though `vcs_release` is disabled** in the `python-semantic-release` step (release
creation happens via a separate `gh release create` step instead); the job-level permission
declaration is what GitHub checks at startup, independent of which step actually consumes
the scope.

**Accuracy note**: `attestations: write` is granted at the job level but is not currently
consumed by any step in this workflow. There is no `actions/attest-build-provenance` step
here; the Sigstore signing step (`sigstore/gh-action-sigstore-python`) only needs `id-token:
write` (OIDC) and `contents: write` (to upload the signing bundle to the release). Keep
granting `attestations: write` for forward compatibility, but if you are diagnosing a signing
failure, check `id-token` and `contents`, not `attestations`.

If `publish-to-pypi: true`, the `publish-pypi` job additionally uses `id-token: write`
(already covered above) to authenticate to PyPI via OIDC Trusted Publishing; it does not need
`contents: read` because it only downloads the previously built artifact and publishes it.

## Troubleshooting

### Run fails with `startup_failure` before the release job starts

**Symptoms**:

```text
This run likely failed due to a workflow file issue.
```

**Solutions**:

1. Confirm the caller's `permissions:` block includes all five scopes the `release` job
   declares: `contents: write`, `id-token: write`, `attestations: write`, `issues: write`,
   and `pull-requests: write` (see [Required Permissions](#required-permissions)). Missing
   `issues: write` or `pull-requests: write` is the most common gap, since some existing
   examples only show three of the five.
2. Verify with `gh run view <run-id> --json conclusion`; a `startup_failure` conclusion
   confirms the grant is still insufficient.

### Job fails: "run-tests is false but skip-tests-reason is empty"

**Symptoms**:

```text
Error: run-tests is false but skip-tests-reason is empty.
Error: Pre-release tests are a required quality gate. To opt out intentionally, supply a
non-empty skip-tests-reason input documenting why.
```

**Solutions**:

1. Supply a non-empty `skip-tests-reason`, for example: `skip-tests-reason: "tests run in
   upstream pipeline X"`.
2. If tests should actually run, remove `run-tests: false` instead.

### Job fails with "This repo uses Poetry"

**Symptoms**:

```text
Error: This repo uses Poetry. The python-release.yml reusable workflow is uv-only by org
policy. Convert this repo to uv before re-enabling Python release automation.
```

**Solutions**:

1. Convert the repository to `uv` before re-enabling `python-release.yml`. Unlike
   `python-ci.yml`, a missing `pyproject.toml` or a Poetry-managed repo fails the job
   outright rather than skipping, since a release with nothing to build is a
   misconfiguration.

### Release triggers on an unexpected tag, or the version string looks wrong

**Symptoms**: a release is created from a tag that was not intended as a release, or the
`version` output does not match expectations.

**Solutions**:

1. In manual mode (`semantic-release: false`), the release job reads the tag from
   `github.event.inputs.tag` or falls back to `github.ref_name`, and computes the version by
   stripping only a leading `v` (`VERSION="${TAG#v}"`). If the caller's trigger is not scoped
   to a `v*` tag pattern (`on: push: tags: ['v*']`), any pushed tag triggers a release.
2. Scope the caller's trigger to the intended tag pattern, and confirm `git tag -l 'v*'`
   matches what you expect before pushing.

### PyPI publish step fails with an OIDC or trusted-publisher error

**Symptoms**: the `publish-pypi` job fails during `uv publish --trusted-publishing always`,
or the job never starts despite `publish-to-pypi: true` and a successful release.

**Solutions**:

1. Configure the Trusted Publisher at
   [pypi.org/manage/account/publishing](https://pypi.org/manage/account/publishing/) using
   the **caller workflow's filename** (not `python-release.yml`, the reusable workflow
   path).
2. Confirm a `pypi` GitHub environment exists in the repository's Settings > Environments;
   the `publish-pypi` job references `environment: name: pypi`, and a missing environment or
   an unmet protection rule (required reviewers, wait timer) blocks the job.
3. Confirm the caller granted `id-token: write` (see Required Permissions above); without it,
   OIDC token issuance fails before `uv publish` runs.

## Additional Resources

- [python-semantic-release documentation](https://python-semantic-release.readthedocs.io/)
- [Sigstore gh-action-sigstore-python](https://github.com/sigstore/gh-action-sigstore-python)
- [PyPI Trusted Publishing Documentation](https://docs.pypi.org/trusted-publishers/)
- [CycloneDX Python](https://github.com/CycloneDX/cyclonedx-python)
