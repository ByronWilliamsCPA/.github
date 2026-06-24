# python-standard-stack.yml -- Standard Python CI Quickstart

The `python-standard-stack.yml` reusable workflow is the recommended starting point
for new Python projects in ByronWilliamsCPA. It bundles the most common CI checks
into a single workflow call.

## What it runs

- Ruff lint and format check
- BasedPyright type checking
- pytest with coverage measurement
- Bandit security scan
- pip-audit dependency vulnerability scan
- Optional: Snyk AI-code-security layer (when `run-snyk: true`)

## Minimal usage

Create `.github/workflows/ci.yml` in your project:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  ci:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-standard-stack.yml@v1
    with:
      python-version: "3.12"
    secrets: inherit
```

## Inputs

| Input | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `python-version` | string | no | `3.12` | Python version to use |
| `source-directory` | string | no | `src` | Source code directory |
| `coverage-threshold` | number | no | `80` | Minimum line coverage percentage |
| `fail-on-high` | boolean | no | `true` | Fail on HIGH or CRITICAL security findings |
| `run-snyk` | boolean | no | `false` | Run the Snyk AI-code-security layer; requires SNYK_TOKEN |

When `run-snyk: true`, pass `SNYK_TOKEN` (via `secrets: inherit` or an explicit
`secrets:` block) and ensure the caller grants `security-events: write`. The Snyk
layer is documented in [python-snyk.md](python-snyk.md).

## Extending the stack

After `python-standard-stack.yml` passes, chain additional workflows for:
- Container builds: `python-docker.yml`
- Coverage upload: `python-codecov.yml`
- SBOM generation: `python-sbom.yml`
- Release: `python-release.yml`

See [docs/workflows/](.) for individual workflow documentation.
