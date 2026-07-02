# python-release.yml -- Reusable release workflow

Builds signed releases with SLSA provenance, SBOM generation, and semantic
versioning. Triggered from a caller that runs on a version tag or release event.

## Minimal usage

```yaml
on:
  push:
    tags: ['v*']

jobs:
  release:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-release.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    permissions:
      contents: write      # create the GitHub release
      id-token: write      # Sigstore keyless signing
      attestations: write  # SLSA provenance attestation
    secrets: inherit
```

## Secrets

No named secrets are declared; the workflow uses the automatic `GITHUB_TOKEN`
and OIDC. Pass `secrets: inherit` if your caller needs to forward additional
secrets.

## Inputs

See `.github/workflows/python-release.yml` for the authoritative input list.
