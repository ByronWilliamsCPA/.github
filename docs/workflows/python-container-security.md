# python-container-security.yml -- Container Image Security Scan

Scans Docker images for vulnerabilities using Trivy. By default, builds the
image from the repository Dockerfile before scanning. Also runs Hadolint
for Dockerfile linting and optionally generates a container SBOM.

## Inputs

| Input | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `image-ref` | string | no | | Container image reference to scan (e.g., `ghcr.io/org/repo:sha`). Omit to build from Dockerfile. |
| `build-image` | boolean | no | `true` | Build image from Dockerfile before scanning |
| `dockerfile-path` | string | no | `./Dockerfile` | Path to Dockerfile |
| `severity-threshold` | string | no | `CRITICAL,HIGH` | Minimum severity to report |
| `fail-on-vulnerabilities` | boolean | no | `true` | Fail if vulnerabilities found at threshold |
| `run-hadolint` | boolean | no | `true` | Run Hadolint Dockerfile linting |
| `upload-sarif` | boolean | no | `true` | Upload SARIF results to GitHub Security tab |

## Secrets

| Secret | Required | Description |
|--------|----------|-------------|
| `DHI_USERNAME` | no | Docker Hardened Images registry username |
| `DHI_PAT` | no | Docker Hardened Images registry personal access token |

## Usage

```yaml
jobs:
  container-scan:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-container-security.yml@main
    with:
      severity-threshold: CRITICAL,HIGH
```
