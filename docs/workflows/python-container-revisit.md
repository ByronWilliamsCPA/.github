# python-container-revisit.yml -- Unfixed CVE Revisit Tracker

Holds container vulnerabilities that have no upstream fix to a revisit
deadline. Scans the image at full scope (no `ignore-unfixed`), then maintains a
single tracker issue in which every unfixed CVE carries a first-seen date and a
revisit due date. Once a due date passes, the run fails.

## Why this exists

`python-container-security.yml` runs pull requests with `ignore-unfixed: true`
so base-image CVEs with no patch available do not block a merge that cannot fix
them. On its own, that is an unbounded suppression: nothing forces a second
look. This workflow is the counterweight. It runs weekly, records the findings
that the PR gate skips, and converts each one into a dated obligation.

## Inputs

| Input | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `image-ref` | string | no | | Container image reference to scan. Omit to build from Dockerfile. |
| `build-image` | boolean | no | `true` | Build image from Dockerfile before scanning |
| `dockerfile-path` | string | no | `./Dockerfile` | Path to Dockerfile |
| `build-context` | string | no | `.` | Docker build context path |
| `image-tag` | string | no | `revisit-scan:latest` | Tag for built image (used when `build-image` is `true`) |
| `severity-threshold` | string | no | `CRITICAL,HIGH` | Severities to track |
| `revisit-horizon-days` | number | no | `90` | Days from first sighting to the revisit deadline |
| `fail-on-overdue` | boolean | no | `true` | Fail the run when a tracked CVE is past its revisit date |
| `issue-label` | string | no | `trivy-unfixed-revisit` | Label identifying the tracker issue |
| `issue-title` | string | no | `Unfixed container CVEs: revisit tracker` | Title of the tracker issue |
| `enable-dhi-login` | boolean | no | `true` | Enable login to Docker Hardened Images (dhi.io) registry |
| `central-checker-ref` | string | no | `main` | Ref of `ByronWilliamsCPA/.github` supplying the tracker script |

## Secrets

| Secret | Required | Description |
|--------|----------|-------------|
| `DHI_USERNAME` | no | Docker Hardened Images registry username |
| `DHI_PAT` | no | Docker Hardened Images registry personal access token |

## Permissions

The calling job must grant `issues: write` in addition to `contents: read`. A
reusable workflow cannot hold a permission its caller did not grant, which is
why the tracker is a separate workflow rather than another job inside
`python-container-security.yml`: adding `issues: write` there would break every
existing caller that grants only `contents: read` and `security-events: write`.

## Usage

```yaml
on:
  schedule:
    - cron: '15 3 * * 1'   # Weekly Monday 3:15 AM UTC
  workflow_dispatch:

jobs:
  container-revisit:
    name: Unfixed CVE Revisit Tracker
    if: github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'
    uses: ByronWilliamsCPA/.github/.github/workflows/python-container-revisit.yml@<sha> # vX.Y.Z
    with:
      dockerfile-path: './Dockerfile'
      severity-threshold: 'CRITICAL,HIGH'
      revisit-horizon-days: 90
      fail-on-overdue: true
    permissions:
      contents: read
      issues: write
```

## How the tracker behaves

| Situation | Result |
|-----------|--------|
| CVE seen for the first time | First seen today, due today + `revisit-horizon-days` |
| CVE already in the tracker | Keeps its original due date; the deadline does not roll forward |
| CVE gone from the scan (fixed upstream or base image moved) | Dropped from the table |
| No unfixed CVEs left | Tracker issue is closed with a comment |
| A due date has passed | Issue is updated first, then the run fails |

The issue body is the state store. The table columns and their ISO dates are a
contract between successive runs, so edit dates in place to re-accept a finding
for another period; do not reformat the table. The workflow writes the updated
body before it fails on overdue findings, so the issue always reflects the
latest scan even on a red run.

## Relationship to `.trivyignore.yaml`

Two revisit mechanisms, two scopes:

- **This workflow** covers the blanket `ignore-unfixed` set: findings nobody has
  explicitly suppressed, which the PR gate skips because no fix exists.
- **`enforce-ignore-expiry` in `python-container-security.yml`** covers explicit
  suppressions: every `.trivyignore.yaml` entry must carry an `expired_at`
  revisit date within the same 90-day horizon.

A finding can move from the first to the second: accept it deliberately, write
the justification into `.trivyignore.yaml` with a dated `expired_at`, and it
leaves the tracker for the suppression file.

## Scripts

- `scripts/track_unfixed_cves.py` renders the issue body and gates on overdue
  findings. Tested by `tests/python/test_track_unfixed_cves.py`.
