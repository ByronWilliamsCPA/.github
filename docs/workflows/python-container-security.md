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
| `build-context` | string | no | `.` | Docker build context path |
| `image-tag` | string | no | `security-scan:latest` | Tag for built image (used when `build-image` is `true`) |
| `severity-threshold` | string | no | `CRITICAL,HIGH` | Minimum severity to report (CRITICAL, HIGH, MEDIUM, LOW) |
| `fail-on-vulnerabilities` | boolean | no | `true` | Fail if vulnerabilities found at threshold |
| `run-hadolint` | boolean | no | `true` | Run Hadolint Dockerfile linting |
| `hadolint-failure-threshold` | string | no | `error` | Hadolint severity to treat as failure (error, warning, info, style, ignore, none) |
| `generate-sbom` | boolean | no | `false` | Generate container SBOM |
| `upload-sarif` | boolean | no | `true` | Upload SARIF results to GitHub Security tab |
| `artifact-retention-days` | number | no | `30` | Days to retain security scan artifacts |
| `enable-dhi-login` | boolean | no | `true` | Enable login to Docker Hardened Images (dhi.io) registry |

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
