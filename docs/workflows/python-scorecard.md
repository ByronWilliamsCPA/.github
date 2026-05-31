# python-scorecard.yml -- Reusable OpenSSF Scorecard workflow

Evaluates repository security health using OpenSSF Scorecard and uploads the
SARIF result to the GitHub Security tab.

> `publish-results` is always treated as false by this workflow. See the
> workflow file's Known Limitations and ADR-001 for the rationale.

## Minimal usage

```yaml
on:
  push:
    branches: [main]
  schedule:
    - cron: '0 0 * * 0'

jobs:
  scorecard:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-scorecard.yml@v1
    with:
      upload-sarif: true
    permissions:
      security-events: write
      contents: read
      actions: read
```

## Secrets

| Secret | Required | Purpose |
|--------|----------|---------|
| `SCORECARD_TOKEN` | no | PAT used by scheduled runs that need broader read access |

## Inputs

See `.github/workflows/python-scorecard.yml` for the authoritative input list.
