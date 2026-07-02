# python-sbom.yml -- Reusable SBOM workflow

Generates a Software Bill of Materials (CycloneDX) and runs vulnerability and
license scanning over it.

## Minimal usage

```yaml
jobs:
  sbom:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-sbom.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    secrets: inherit
```

## Secrets

All optional, needed only for private dependency sources:

| Secret | Purpose |
|--------|---------|
| `INFISICAL_CLIENT_ID` / `INFISICAL_CLIENT_SECRET` | Fetch secrets from Infisical |
| `DHI_USERNAME` / `DHI_PAT` | Authenticate to a private (DHI) registry |

## Inputs

See `.github/workflows/python-sbom.yml` for the authoritative input list.
