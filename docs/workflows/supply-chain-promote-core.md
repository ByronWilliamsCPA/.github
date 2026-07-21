# supply-chain-promote-core.yml -- Scan, publish, sign, and lock-update chokepoint (Reusable)

The shared trust core for both upstream paths (mirror and build) and both destinations
(public `container-images`, private `homelab-infra`). Given a verified source, either an
upstream digest from `supply-chain-mirror-verify.yml` or a locally-built OCI tar from
`supply-chain-build-verify.yml`, it scans the candidate with Grype and Snyk before any
public push, publishes to GHCR only on a scan pass, generates SBOMs, signs and attests with
Cosign, and (opt-in) opens a pull request to append the promotion to an approved-lock file.
This is the single chokepoint where scan-before-publish and sign-after-publish live once for
every caller.

## Quick Reference

- **Workflow**: `.github/workflows/supply-chain-promote-core.yml`
- **Type**: Reusable (`workflow_call`)
- **Role**: shared publish core for both the mirror path and the build path
- **Jobs**: `scan` (pre-publish, no publish permissions), `publish` (GHCR push, sign, attest),
  `update-lock` (opt-in PR to `lock_file`, only on `main`)
- **Fed by**: `supply-chain-mirror-verify.yml` (`source_kind: registry`) or
  `supply-chain-build-verify.yml` (`source_kind: oci-tar`)

## Minimal usage

```yaml
jobs:
  verify:
    uses: ByronWilliamsCPA/.github/.github/workflows/supply-chain-mirror-verify.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    with:
      upstream_registry: dhi.io
      upstream_name: postgres
      upstream_tag: "17"

  promote:
    needs: verify
    uses: ByronWilliamsCPA/.github/.github/workflows/supply-chain-promote-core.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    with:
      image_id: dhi-postgres-17
      source_kind: registry
      source_ref: ${{ needs.verify.outputs.source_ref }}
      ghcr_name: dhi-postgres
      ghcr_tag: "17"
      write_lock: true
    secrets:
      SNYK_TOKEN: ${{ secrets.SNYK_TOKEN }}
      UPSTREAM_REGISTRY_USERNAME: ${{ secrets.DHI_REGISTRY_USERNAME }}
      UPSTREAM_REGISTRY_TOKEN: ${{ secrets.DHI_REGISTRY_TOKEN }}
```

## Inputs

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `image_id` | string | Yes | -- | Unique catalog slug for this image family version |
| `source_kind` | string | No | `registry` | `"registry"` (pull `source_ref`) or `"oci-tar"` (download `source_artifact`) |
| `source_ref` | string | No | `""` | For `source_kind=registry`, the verified upstream ref with digest |
| `source_artifact` | string | No | `""` | For `source_kind=oci-tar`, the uploaded artifact name holding `image.tar` |
| `ghcr_name` | string | Yes | -- | Image name under `ghcr.io/<owner>/` (single path segment; e.g. `dhi-postgres`) |
| `ghcr_tag` | string | Yes | -- | Tag to publish to GHCR |
| `platform` | string | No | `linux/amd64` | Target platform |
| `lock_file` | string | No | `catalog/approved-lock.yaml` | Approved-lock path to update (canonical or private overlay) |
| `write_lock` | boolean | No | `false` | When true and on `main`, append the promotion entry to `lock_file` |
| `snyk_threshold` | string | No | `high` | Snyk severity threshold that blocks promotion |
| `grype_fail_on` | string | No | `high` | Minimum severity that blocks promotion (`negligible`\|`low`\|`medium`\|`high`\|`critical`) |
| `sign` | boolean | No | `true` | When true and on `main`, cosign sign + attest the published digest |

## Outputs

| Name | Description |
|------|-------------|
| `promoted` | `true` once the `publish` job completes |
| `target_ref` | GHCR reference published (`ghcr.io/<owner>/<ghcr_name>:<ghcr_tag>`) |
| `target_digest` | `sha256` digest of the published image |

## Secrets

| Name | Required | Description |
|------|----------|-------------|
| `SNYK_TOKEN` | No | Enables the Snyk gate in the `scan` job; the gate is skipped (not failed) when absent |
| `UPSTREAM_REGISTRY_USERNAME` | No | Upstream registry username for the `scan` job's `crane pull`; required when `source_kind=registry` and the upstream is authenticated (e.g. `dhi.io`) |
| `UPSTREAM_REGISTRY_TOKEN` | No | Token/password paired with `UPSTREAM_REGISTRY_USERNAME` |

## Required Permissions

```yaml
permissions:
  contents: read
  security-events: write   # scan job: SARIF upload
  packages: write           # publish job: push to GHCR
  id-token: write           # publish job: cosign keyless signing
  attestations: write       # publish job: build provenance attestation
  pull-requests: write      # update-lock job: opens the lock PR
```

Job-level grants differ by job on purpose: `scan` gets only `contents: read` and
`security-events: write` (no publish credentials reach the scan stage); `publish` adds
`packages: write`, `id-token: write`, `attestations: write`; `update-lock` uses
`contents: write` and `pull-requests: write` and runs only when `write_lock: true`,
`publish` succeeded, and `github.ref == 'refs/heads/main'`.

## Troubleshooting

### source_ref must include @sha256

```text
::error::source_ref must include @sha256:<64hex>; got '<value>'
```

`source_kind: registry` was set but `source_ref` is a mutable tag, not a digest-pinned
reference. Pass `needs.<mirror-verify-job>.outputs.source_ref` directly; do not
hand-construct a tag-based ref, since that bypasses the verified-digest trust model.

### Grype or Snyk gate blocks the scan job

Grype's `--fail-on <grype_fail_on>` or Snyk's `--severity-threshold=<snyk_threshold>` exits
non-zero when a vulnerability at or above the configured severity is found in the candidate
image, before anything is pushed. The Grype SARIF is still uploaded to the Security tab even
on a failing run for review. Either remediate the finding in the base/build, or (with
appropriate approval) raise `grype_fail_on`/`snyk_threshold` for that specific promotion.

### GHCR digest has unexpected shape

```text
::error::GHCR digest has unexpected shape: <value>
```

`crane digest` against the freshly-pushed GHCR target did not return a well-formed
`sha256:<64hex>` value, usually a transient GHCR read-after-write issue or an interrupted
`crane copy`/`crane push`. Re-run the `publish` job; if it recurs, check GHCR status before
assuming a code issue.

### Lock PR could not be created or located

```text
::error::failed to create or locate the lock PR for <lock-branch>
```

`update-lock` pushed the branch but `gh pr create` failed and the `gh pr view` fallback also
found nothing, typically a `GITHUB_TOKEN` permission or rate-limit issue. Check the
`::warning::gh pr create returned no URL; stderr: ...` line immediately above it in the log
for the underlying `gh` error before retrying.

### Could not enable auto-merge

```text
::warning::could not enable auto-merge; <pr-url> left for manual merge
```

The lock PR was opened successfully but the caller repository does not have auto-merge
enabled. This is non-fatal; the promotion still succeeded and the PR is left open for a
manual merge.

## Related Workflows

- `supply-chain-mirror-verify.md`: feeds this workflow with `source_kind: registry`.
- `supply-chain-build-verify.md`: feeds this workflow with `source_kind: oci-tar`.
- `supply-chain-consume-verify.md`: the downstream gate a deployer runs against the
  `target_ref`/`target_digest` this workflow publishes and signs.
