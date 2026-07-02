# python-docker.yml -- Docker Build and Push

Builds a Docker image and optionally pushes it to GitHub Container Registry
(GHCR) or another registry. Includes Trivy vulnerability scanning, SBOM
generation, SLSA provenance attestation, and PR comments with build info.

## Inputs

| Input | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `dockerfile` | string | no | `Dockerfile` | Path to Dockerfile |
| `context` | string | no | `.` | Docker build context |
| `platforms` | string | no | `linux/amd64,linux/arm64` | Target platforms (comma-separated) |
| `build-args` | string | no | | Build arguments (newline-separated KEY=VALUE) |
| `registry` | string | no | `ghcr.io` | Container registry |
| `image-name` | string | no | `github.repository` | Image name (default: repo slug when empty) |
| `push` | boolean | no | `false` | Push image to registry |
| `push-on-fork` | boolean | no | `false` | Allow push from fork PRs (security risk) |
| `tag-latest` | boolean | no | `false` | Tag as latest (for releases and main branch) |
| `tag-semver` | boolean | no | `false` | Generate semver tags from release tag |
| `tag-sha` | boolean | no | `true` | Tag with commit SHA |
| `tag-pr` | boolean | no | `true` | Tag with PR number (for PR builds) |
| `additional-tags` | string | no | | Additional tags (newline-separated) |
| `enable-trivy-scan` | boolean | no | `true` | Enable Trivy vulnerability scanning |
| `trivy-severity` | string | no | `CRITICAL,HIGH` | Trivy severity threshold (CRITICAL,HIGH,MEDIUM,LOW) |
| `trivy-fail-on-vuln` | boolean | no | `false` | Fail build if vulnerabilities found |
| `enable-sbom` | boolean | no | `true` | Generate Software Bill of Materials |
| `enable-provenance` | boolean | no | `true` | Generate SLSA provenance attestation |
| `enable-pr-comment` | boolean | no | `true` | Add sticky comment to PR with build info |
| `enable-dhi-login` | boolean | no | `true` | Enable login to Docker Hardened Images (dhi.io) registry |

## Secrets

| Secret | Required | Description |
|--------|----------|-------------|
| `DHI_USERNAME` | no | Docker Hardened Images registry username |
| `DHI_PAT` | no | Docker Hardened Images registry personal access token |

## Usage

```yaml
jobs:
  build:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-docker.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    with:
      image-name: my-app
      push: ${{ github.ref == 'refs/heads/main' }}
      tag-latest: ${{ github.ref == 'refs/heads/main' }}
```
