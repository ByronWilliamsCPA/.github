# python-qlty-coverage.yml -- Reusable Qlty coverage upload

Uploads test coverage to Qlty Cloud for centralized quality tracking. Call it
after a job that produces a coverage report artifact.

## Minimal usage

```yaml
jobs:
  coverage:
    needs: test
    uses: ByronWilliamsCPA/.github/.github/workflows/python-qlty-coverage.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    secrets:
      QLTY_COVERAGE_TOKEN: ${{ secrets.QLTY_COVERAGE_TOKEN }}
```

## Secrets

| Secret | Required | Purpose |
|--------|----------|---------|
| `QLTY_COVERAGE_TOKEN` | yes | Authenticates the coverage upload to Qlty Cloud |

## Inputs

See `.github/workflows/python-qlty-coverage.yml` for the authoritative input list.
