# python-reuse.yml -- Reusable REUSE compliance workflow

Validates FSFE REUSE 3.0 specification compliance for license management
(every file carries SPDX licensing information).

## Minimal usage

```yaml
name: REUSE Compliance

on:
  pull_request:
  push:
    branches: [main]

jobs:
  reuse:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-reuse.yml@v1
```

## Secrets

None.

## Inputs

See `.github/workflows/python-reuse.yml` for the authoritative input list.
