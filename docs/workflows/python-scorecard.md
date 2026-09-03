# python-scorecard.yml -- Reusable OpenSSF Scorecard workflow

Evaluates repository security health using OpenSSF Scorecard and publishes the
SARIF result as a workflow artifact. GitHub Security tab upload was removed;
that path required paid GitHub Advanced Security.

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
    uses: ByronWilliamsCPA/.github/.github/workflows/python-scorecard.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    permissions:
      contents: read
      actions: read
```

## Secrets

| Secret | Required | Purpose |
|--------|----------|---------|
| `SCORECARD_TOKEN` | no | PAT used by scheduled runs that need broader read access |

## Inputs

See `.github/workflows/python-scorecard.yml` for the authoritative input list.
