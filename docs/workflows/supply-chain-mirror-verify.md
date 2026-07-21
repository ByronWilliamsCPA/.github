# supply-chain-mirror-verify.yml -- Upstream digest resolution and signature verification (Reusable)

Front half of the MIRROR path in the container supply chain. Given an upstream registry,
image name, and mutable tag, this workflow resolves the exact `sha256` digest with `crane`
and, fail-closed by default, verifies the upstream signer identity with `cosign`. It never
pushes anywhere; the verified `source_ref` it outputs is handed to
`supply-chain-promote-core.yml`, which is the only job in the chain allowed to publish.

## Quick Reference

- **Workflow**: `.github/workflows/supply-chain-mirror-verify.yml`
- **Type**: Reusable (`workflow_call`)
- **Role**: front half of the MIRROR path (an existing public upstream image, e.g. a Docker
  Hardened Image or Google Distroless base)
- **Trust root**: the external upstream signer (cosign certificate identity + OIDC issuer)
- **Feeds into**: `supply-chain-promote-core.yml` with `source_kind: registry`

## Minimal usage

```yaml
jobs:
  verify:
    uses: ByronWilliamsCPA/.github/.github/workflows/supply-chain-mirror-verify.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    with:
      upstream_registry: dhi.io
      upstream_name: postgres
      upstream_tag: "17"
      expected_identity_regexp: '^https://github\.com/docker/...'
    secrets:
      DHI_REGISTRY_USERNAME: ${{ secrets.DHI_REGISTRY_USERNAME }}
      DHI_REGISTRY_TOKEN: ${{ secrets.DHI_REGISTRY_TOKEN }}

  promote:
    needs: verify
    uses: ByronWilliamsCPA/.github/.github/workflows/supply-chain-promote-core.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    with:
      image_id: dhi-postgres-17
      source_kind: registry
      source_ref: ${{ needs.verify.outputs.source_ref }}
      ghcr_name: dhi-postgres
      ghcr_tag: "17"
```

## Inputs

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `upstream_registry` | string | Yes | -- | Source registry hostname (e.g. `dhi.io`, `gcr.io`) |
| `upstream_name` | string | Yes | -- | Image name without registry prefix (e.g. `postgres`) |
| `upstream_tag` | string | Yes | -- | Upstream mutable tag to resolve to a digest |
| `platform` | string | No | `linux/amd64` | Target platform for digest resolution |
| `require_upstream_signature` | boolean | No | `true` | Fail closed unless the upstream signature verifies |
| `expected_identity_regexp` | string | No | `""` | Cosign certificate-identity regexp for the upstream signer |
| `expected_issuer_regexp` | string | No | `^https://token\.actions\.githubusercontent\.com$` | Cosign certificate-oidc-issuer regexp for the upstream signer |

## Outputs

| Name | Description |
|------|-------------|
| `source_ref` | Fully-qualified upstream reference with resolved digest (`registry/name@sha256:...`) |
| `source_digest` | `sha256` digest resolved from the upstream registry |
| `verified` | `true` when the upstream signature verified, or verification was not required |

## Secrets

| Name | Required | Description |
|------|----------|-------------|
| `DHI_REGISTRY_USERNAME` | No | Username for an authenticated upstream registry (e.g. `dhi.io`); omit for anonymous pulls |
| `DHI_REGISTRY_TOKEN` | No | Token/password paired with `DHI_REGISTRY_USERNAME` |

## Required Permissions

```yaml
permissions:
  contents: read
```

The workflow declares top-level `permissions: {}` and grants its single `verify` job only
`contents: read`; it never requests `packages:write` or `id-token:write` because it never
publishes.

## Troubleshooting

### Resolved digest has unexpected shape

```text
::error::Resolved digest has unexpected shape:
```

`crane digest` failed (bad tag, unreachable registry, or wrong/missing credentials for an
authenticated upstream) and returned an empty or malformed value. Check that
`upstream_tag` exists at `upstream_registry`/`upstream_name`, and that
`DHI_REGISTRY_USERNAME`/`DHI_REGISTRY_TOKEN` are set when the upstream requires auth (an
anonymous pull against an authenticated registry fails the same way).

### Upstream signature verification FAILED

```text
::error::Upstream signature verification FAILED for <ref> (fail-closed).
```

`cosign verify` did not find a signature matching `expected_identity_regexp` /
`expected_issuer_regexp` at the resolved digest. Either the upstream image is genuinely
unsigned by the expected signer, or the regexp is wrong for that publisher. Confirm the real
signer identity for the upstream (e.g. the DHI or Distroless release pipeline) before
relaxing anything; do not widen the regexp to `.*` to make this pass.

### expected_identity_regexp is empty or '.*'

```text
::error::require_upstream_signature=true but expected_identity_regexp is empty or '.*'.
```

`require_upstream_signature` defaults to `true`, so a caller must pin a real identity
regexp. An empty or wildcard value would only prove *a* signature exists, not who signed it,
so the workflow refuses to run with one.

## Related Workflows

- `supply-chain-build-verify.md`: the alternate front half for internally-built images (no
  upstream signer to verify); feeds the same `supply-chain-promote-core.yml`.
- `supply-chain-promote-core.md`: consumes this workflow's `source_ref` output
  (`source_kind: registry`), scans, publishes to GHCR, and signs.
- `supply-chain-consume-verify.md`: the downstream gate a deployer runs against the image
  `supply-chain-promote-core.yml` eventually publishes.
