# supply-chain-consume-verify.yml -- Downstream image provenance gate (Reusable)

Consumer-side gate of the container supply chain. A downstream deployer (for example, a
Portainer or compose repository) calls this before deploying a GHCR image to prove that the
image is recorded in an approved-lock (when a lock file is given) and carries a valid Cosign
signature and attestation from the expected signer identity, never merely "a" signature.
Verifying the expected identity is the point: it is the half that catches trust-laundering,
where an attacker presents a technically-valid signature from an identity nobody approved.

## Quick Reference

- **Workflow**: `.github/workflows/supply-chain-consume-verify.yml`
- **Type**: Reusable (`workflow_call`)
- **Role**: terminal gate, runs in the deploying repository before an image is deployed
- **Rollout pattern**: `enforce: false` (warn mode, always exits 0) then `enforce: true`
  (fail-closed) once the bake period is over
- **Fed by**: an image published (and signed) by `supply-chain-promote-core.yml`

## Minimal usage

```yaml
jobs:
  verify-image:
    uses: ByronWilliamsCPA/.github/.github/workflows/supply-chain-consume-verify.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    with:
      image_ref: 'ghcr.io/byronwilliamscpa/dhi-postgres@sha256:abc...def'
      expected_identity_regexp: '^https://github\.com/ByronWilliamsCPA/.+$'
      lock_file: 'approved-images.lock'
      require_attestation: true
      enforce: false   # warn mode first, flip to true to fail closed
```

## Inputs

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `image_ref` | string | Yes | -- | GHCR reference including digest (e.g. `ghcr.io/org/app@sha256:...`) |
| `expected_identity_regexp` | string | Yes | -- | Regexp the signer certificate identity must match; never empty, never `.*` |
| `expected_issuer_regexp` | string | No | `^https://token\.actions\.githubusercontent\.com$` | Regexp the OIDC issuer must match |
| `lock_file` | string | No | `""` | Optional path to an approved-lock the digest must appear in; empty skips the check |
| `require_attestation` | boolean | No | `true` | Also require a valid cosign attestation (cyclonedx) |
| `enforce` | boolean | No | `false` | Fail closed on verification failure when true; warn mode (exit 0) when false |

## Outputs

| Name | Description |
|------|-------------|
| `verified` | `true` when all checks passed, `false` otherwise |

## Secrets

None. This workflow declares no `secrets:` block.

## Required Permissions

```yaml
permissions:
  contents: read
```

The workflow declares top-level `permissions: {}` and grants its single `verify` job only
`contents: read`, used to check out the caller repository so an optional `lock_file` can be
read. There is no publish or sign step.

## Troubleshooting

### image_ref must include a @sha256 digest

```text
::error::image_ref must include a @sha256:<64hex> digest; got '<value>'
```

`image_ref` is a mutable tag, not a digest-pinned reference. A tag cannot be verified against
a specific signature/attestation; pass the digest-qualified reference that
`supply-chain-promote-core.yml` published (`target_ref`@`target_digest`).

### expected_identity_regexp must be a specific pattern

```text
::error::expected_identity_regexp must be a specific pattern, not empty or '.*'
```

An empty or match-everything identity regexp (`.*`, `^.*$`, `^.*`, `.*$`) would accept any
signer, defeating trust-laundering detection, so the workflow refuses to run with one. Pin
the actual expected signer, typically the caller repository's own GitHub Actions OIDC
identity.

### Signature verification failed

```text
Signature verification failed
```

`cosign verify` found no signature at `image_ref` matching `expected_identity_regexp` /
`expected_issuer_regexp`. In `enforce: true` mode this becomes:

```text
::error::image provenance verification failed for <image_ref> (enforce mode)
```

and the job fails. In `enforce: false` (bake period) it is instead:

```text
::warning::image provenance verification failed for <image_ref> (WARN mode, exit 0)
```

and the job still exits 0 with `verified=false`, so a deployer relying on the `verified`
output (rather than job status) must check it explicitly during the warn period.

### digest not found in approved-lock

```text
::error::digest <digest> not found in approved-lock <lock_file>
```

(only when `enforce: true`; otherwise this is a warning and the check continues.) The image
digest is not recorded in `lock_file`. Confirm the image actually went through
`supply-chain-promote-core.yml` with `write_lock: true`, and that `lock_file` points at the
same catalog the promotion wrote to (canonical vs. private overlay).

## Related Workflows

- `supply-chain-promote-core.md`: publishes and signs the image this workflow verifies.
- `supply-chain-mirror-verify.md`: the ultimate upstream origin for a mirrored image, feeding
  `supply-chain-promote-core.yml`.
- `supply-chain-build-verify.md`: the ultimate origin for an internally-built image, feeding
  `supply-chain-promote-core.yml`.
