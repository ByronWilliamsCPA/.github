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
    uses: ByronWilliamsCPA/.github/.github/workflows/python-standard-stack.yml@main
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

## Extending the stack

After `python-standard-stack.yml` passes, chain additional workflows for:
- Container builds: `python-docker.yml`
- Coverage upload: `python-codecov.yml`
- SBOM generation: `python-sbom.yml`
- Release: `python-release.yml`

See [docs/workflows/](.) for individual workflow documentation.
