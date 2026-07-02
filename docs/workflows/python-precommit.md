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
    uses: ByronWilliamsCPA/.github/.github/workflows/python-precommit.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    secrets: inherit
```

## Secrets

None.

## Inputs

See `.github/workflows/python-precommit.yml` for the authoritative input list.
