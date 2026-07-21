# supply-chain-build-verify.yml -- Base validation and no-push image build (Reusable)

Front half of the BUILD path in the container supply chain. This path builds a container
image from internal source code, so there is no upstream signature to verify; the trust root
is "reviewed source plus verified base images." The workflow validates that every Dockerfile
`FROM` base is digest-pinned and present in an approved-lock file, optionally checks
`uv.lock` freshness, refuses secret-shaped `ARG`/`ENV` names, and builds the image to a local
tar. It never pushes or signs; that happens in `supply-chain-promote-core.yml`.

## Quick Reference

- **Workflow**: `.github/workflows/supply-chain-build-verify.yml`
- **Type**: Reusable (`workflow_call`)
- **Role**: front half of the BUILD path (image built from this repository's own Dockerfile)
- **Trust root**: reviewed source plus base images already present in the approved lock
- **Feeds into**: `supply-chain-promote-core.yml` with `source_kind: oci-tar`

## Minimal usage

```yaml
jobs:
  build:
    uses: ByronWilliamsCPA/.github/.github/workflows/supply-chain-build-verify.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    with:
      image_id: my-service
      dockerfile_path: ./Dockerfile
      build_context: .
      platform: linux/amd64
      lock_file: catalog/approved-lock.yaml
      require_uv_lock: true
      build_args: |
        VERSION=1.2.3
        COMMIT_SHA=${{ github.sha }}

  promote:
    needs: build
    uses: ByronWilliamsCPA/.github/.github/workflows/supply-chain-promote-core.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    with:
      image_id: my-service
      source_kind: oci-tar
      source_artifact: ${{ needs.build.outputs.artifact_name }}
      ghcr_name: my-service
      ghcr_tag: "1.2.3"
```

## Inputs

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `image_id` | string | Yes | -- | Logical image identifier used to tag the local build (e.g. `my-service`) |
| `dockerfile_path` | string | No | `./Dockerfile` | Path to the Dockerfile to build |
| `build_context` | string | No | `.` | Docker build context directory |
| `platform` | string | No | `linux/amd64` | Target platform for the build |
| `lock_file` | string | No | `catalog/approved-lock.yaml` | Approved-lock file every `FROM` base digest must appear in |
| `require_uv_lock` | boolean | No | `true` | Fail unless `uv.lock` is up to date (`uv lock --check`) |
| `build_args` | string | No | `""` | Newline-separated `KEY=VALUE` build args passed to buildx |

## Outputs

| Name | Description |
|------|-------------|
| `local_tar` | Path to the built OCI/docker image tar on the runner |
| `artifact_name` | GHA artifact name holding the built image tar; pass to promote-core as `source_artifact` |
| `built` | `true` when the image build succeeded |

## Secrets

None. This workflow declares no `secrets:` block.

## Required Permissions

```yaml
permissions:
  contents: read
```

The workflow declares top-level `permissions: {}` and grants its single `build` job only
`contents: read` for checkout; there is no push or sign step, so no `packages:write` or
`id-token:write` is needed.

## Troubleshooting

### Base image is not digest-pinned

```text
::error::Base image is not digest-pinned: <base>
```

A `FROM` line uses a mutable tag (e.g. `postgres:17`) instead of a `name@sha256:<64hex>`
reference. Re-point the Dockerfile at the digest-pinned reference produced by
`supply-chain-mirror-verify.yml` or a prior `supply-chain-promote-core.yml` publish; a
`FROM <stage>` that re-references an earlier named build stage is exempt and does not
trigger this.

### Base digest not in approved lock

```text
::error::Base digest not in approved lock (<lock_file>): <base>
```

The base is digest-pinned but that exact digest string does not appear anywhere in
`lock_file`. Either the base was never promoted through `supply-chain-promote-core.yml`
(`write_lock: true`), or `lock_file` points at the wrong catalog (canonical vs. a private
overlay). Confirm the digest exists in the intended lock before retrying.

### UV_INSTALLER_SHA256 must be set before this workflow is wired

```text
::error::UV_INSTALLER_SHA256 must be set before this workflow is wired.
```

The `uv.lock` gate step pins the uv installer script by checksum, but that checksum is a
hardcoded step-level value in the reusable workflow itself (not a caller-facing input) and
ships blank. It fails closed rather than skip the integrity check silently. Until the
reusable workflow's `UV_INSTALLER_SHA256` is populated for the pinned `UV_VERSION`, every
caller with `require_uv_lock: true` (the default) hits this error; set
`require_uv_lock: false` as a temporary workaround, or fix the checksum in the reusable
workflow itself.

### require_uv_lock=true but no uv.lock found

```text
::error::require_uv_lock=true but no uv.lock found in <build_context>
```

`build_context` has no `uv.lock`. Either commit a lockfile at that path, pass the correct
`build_context`, or set `require_uv_lock: false` if the image intentionally has no Python
dependency lock.

### Secret-shaped ARG/ENV found

```text
::error::Secret-shaped ARG/ENV found in <dockerfile_path>.
```

The Dockerfile declares an `ARG` or `ENV` whose name matches a secret-shaped pattern
(`PASSWORD`, `SECRET`, `TOKEN`, `APIKEY`, `API_KEY`, `AWS_SECRET`, `PRIVATE_KEY`). Remove the
build-time secret from the Dockerfile and use BuildKit `--mount=type=secret` instead, since
an `ARG`/`ENV` value is baked into image history.

## Related Workflows

- `supply-chain-mirror-verify.md`: the alternate front half for existing upstream images;
  feeds the same `supply-chain-promote-core.yml`.
- `supply-chain-promote-core.md`: consumes this workflow's `artifact_name` output
  (`source_kind: oci-tar`), scans, publishes to GHCR, and signs.
- `supply-chain-consume-verify.md`: the downstream gate a deployer runs against the image
  `supply-chain-promote-core.yml` eventually publishes.
