# python-precommit.yml -- Reusable pre-commit workflow

Runs the repository's `pre-commit` hooks against the entire repository in the
project virtualenv, so the same hooks enforced locally also run in CI.

## Minimal usage

```yaml
name: Pre-commit

on:
  pull_request:
  push:
    branches: [main]

jobs:
  pre-commit:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-precommit.yml@v1
    secrets: inherit
```

## Secrets

None.

## Inputs

See `.github/workflows/python-precommit.yml` for the authoritative input list.
