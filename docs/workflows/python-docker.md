# python-docker.yml -- Docker Build and Push

Builds a Docker image and optionally pushes it to GitHub Container Registry
(GHCR) or another registry. Includes Trivy vulnerability scanning, SBOM
generation, SLSA provenance attestation, and PR comments with build info.

## Inputs

| Input | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `dockerfile` | string | no | `Dockerfile` | Path to Dockerfile |
| `context` | string | no | `.` | Docker build context |
| `platforms` | string | no | `linux/amd64` | Target platforms (comma-separated) |
| `image-name` | string | no | `github.repository` | Image name (without registry prefix) |
| `push` | boolean | no | `false` | Push image to registry |
| `tag-latest` | boolean | no | `false` | Tag as latest (for releases and main branch) |
| `tag-sha` | boolean | no | `true` | Tag with commit SHA |
| `enable-trivy-scan` | boolean | no | `true` | Enable Trivy vulnerability scanning |
| `enable-sbom` | boolean | no | `true` | Generate Software Bill of Materials |
| `enable-provenance` | boolean | no | `true` | Generate SLSA provenance attestation |

## Secrets

| Secret | Required | Description |
|--------|----------|-------------|
| `DHI_USERNAME` | no | Docker Hardened Images registry username |
| `DHI_PAT` | no | Docker Hardened Images registry personal access token |

## Usage

```yaml
jobs:
  build:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-docker.yml@main
    with:
      image-name: my-app
      push: ${{ github.ref == 'refs/heads/main' }}
      tag-latest: ${{ github.ref == 'refs/heads/main' }}
```
