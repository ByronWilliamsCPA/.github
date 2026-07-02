# python-slsa.yml -- SLSA provenance workflow

Generates SLSA build provenance for release artifacts by calling the official
SLSA GitHub generator.

> This workflow itself calls the SLSA generator reusable workflow. GitHub does
> not allow nested reusable-workflow calls, so `python-slsa.yml` must be called
> directly by a caller's job: it cannot be wrapped by another reusable workflow.
> See ADR-001 and the audit's ARCH-01 finding.

## Minimal usage

```yaml
jobs:
  build:
    # ... produces base64-encoded subject hashes as an output ...
  provenance:
    needs: build
    uses: ByronWilliamsCPA/.github/.github/workflows/python-slsa.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    with:
      base64-subjects: ${{ needs.build.outputs.hashes }}
    permissions:
      id-token: write   # Sigstore signing
      contents: write   # attach provenance to the release
      actions: read
```

## Inputs

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `base64-subjects` | string | yes | Base64-encoded subject hashes to attest |

See `.github/workflows/python-slsa.yml` for the full input list.

## Secrets

None.
