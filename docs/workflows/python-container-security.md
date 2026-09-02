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
| `ignore-unfixed` | boolean | no | `false` | Ignore vulnerabilities that have no available fix |
| `enforce-ignore-expiry` | boolean | no | `true` | Require a revisit date (`expired_at`) on every `.trivyignore.yaml` entry |
| `ignore-expiry-horizon-days` | number | no | `90` | Furthest a suppression revisit date may be set from today |
| `allow-legacy-trivyignore` | boolean | no | `false` | Tolerate a plain-text `.trivyignore`, which cannot carry revisit dates |
| `central-checker-ref` | string | no | `main` | Ref of `ByronWilliamsCPA/.github` supplying the revisit-date checker |
| `run-hadolint` | boolean | no | `true` | Run Hadolint Dockerfile linting |
| `hadolint-failure-threshold` | string | no | `error` | Hadolint severity to treat as failure (error, warning, info, style, ignore, none) |
| `generate-sbom` | boolean | no | `false` | Generate container SBOM |
| `upload-sarif` | boolean | no | `true` | Deprecated: SARIF upload to the GitHub Security tab was removed (it required paid GitHub Advanced Security). Accepted for backward compatibility; no longer has any effect. SARIF results are always published as workflow artifacts. |
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
    uses: ByronWilliamsCPA/.github/.github/workflows/python-container-security.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    with:
      severity-threshold: CRITICAL,HIGH
```

## Scan scope: PR gate vs weekly audit

Base-image CVEs frequently have no upstream patch. Failing a pull request on
them gives the author nothing to act on, so the recommended caller pattern
splits the scan into two scopes:

```yaml
on:
  pull_request:
    branches: [main]
  push:
    branches: [main]
  schedule:
    - cron: '15 3 * * 1'   # Weekly Monday 3:15 AM UTC
  workflow_dispatch:
  merge_group:

jobs:
  container-security:
    # Pin the first release that contains `ignore-unfixed`. The SHA below
    # predates the input; copying it verbatim yields an "unexpected input"
    # error.
    uses: ByronWilliamsCPA/.github/.github/workflows/python-container-security.yml@<sha> # vX.Y.Z
    with:
      severity-threshold: CRITICAL,HIGH
      fail-on-vulnerabilities: true
      ignore-unfixed: ${{ github.event_name == 'pull_request' || github.event_name == 'merge_group' }}
```

- **Pull request and merge queue:** `ignore-unfixed: true`. Only findings with
  an available fix block the merge.
- **Push to main, weekly cron, manual dispatch:** `ignore-unfixed: false`. The
  full inventory is scanned; the SARIF report is published as the
  `container-security-reports` workflow artifact and in the weekly run
  summary.

Keep push-to-main on the full scan so unfixed base-image CVEs stay visible in
the default-branch artifact record, not just in the reduced PR-scope scan.

SARIF results are published as a workflow artifact (`container-security-reports`
for Trivy, `hadolint-results` for Hadolint), not uploaded to the GitHub
Security tab. That upload path required paid GitHub Advanced Security and has
been removed.

## Suppression revisit dates

A Trivy suppression with no expiry is a permanent one: the finding leaves every
scan and nothing forces a second look. The `Suppression Revisit Dates` job
enforces a revisit date on each entry in `.trivyignore.yaml`:

```yaml
vulnerabilities:
  - id: CVE-2026-0001
    statement: No upstream fix for the base image; rebase tracked in #505.
    expired_at: 2026-11-14
```

The job fails when an entry:

- has no `expired_at`, or no `statement` explaining the suppression
- carries a revisit date that has already passed
- carries a revisit date more than `ignore-expiry-horizon-days` (90 by default)
  from today
- sits under a top-level key Trivy does not read, which would make the
  suppression silently ineffective

Entries due within 14 days are reported as warnings, not failures.

Both spellings are covered. The scan steps and the validation job each detect
`.trivyignore.yaml`, falling back to `.trivyignore.yml`, and use the same
resolved path, so a suppression cannot be honoured at scan time while escaping
the revisit-date check.

Passing the file explicitly is required: Trivy's default ignore file is the
plain-text `.trivyignore` and it does not auto-detect the YAML variant, so a
dated suppression file that is not passed through would be silently inert.

The legacy plain-text `.trivyignore` has no expiry field at all, so its presence
fails the job. Migrate the entries to `.trivyignore.yaml` with a date on each,
or set `allow-legacy-trivyignore: true` to downgrade it to a warning.

Trivy stops honouring an entry once `expired_at` passes, so an expired
suppression means the finding is back in the gate anyway; failing on the date
turns that surprise into a scheduled decision.

Findings that nobody suppressed explicitly, the ones the PR gate skips because
no fix exists, are tracked separately by
[python-container-revisit.yml](python-container-revisit.md).

## Scripts

- `scripts/check_trivy_ignore_expiry.py` validates `.trivyignore.yaml` revisit
  dates. Tested by `tests/python/test_check_trivy_ignore_expiry.py`.
