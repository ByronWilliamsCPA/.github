# python-security-analysis.yml -- Reusable security analysis workflow

Comprehensive security scanning with CodeQL, Bandit, OSV-Scanner, and
Dependency Review. Each scanner can be toggled via inputs.

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
      security-events: write  # upload SARIF
      contents: read
      actions: read
    secrets: inherit
```

## Inputs (selected)

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| `source-directory` | string | `src` | Source directory to scan |
| `run-codeql` | boolean | `true` | Run CodeQL analysis |
| `run-bandit` | boolean | `true` | Run Bandit static analysis |
| `run-osv` | boolean | `true` | Run OSV Scanner |
| `fail-on-high` | boolean | `true` | Fail on HIGH/CRITICAL findings |

See `.github/workflows/python-security-analysis.yml` for the full input list.

## Secrets

None (uses the automatic `GITHUB_TOKEN`).
