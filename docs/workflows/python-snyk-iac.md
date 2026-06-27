# python-snyk-iac.yml -- Snyk IaC Scanning Layer

The `python-snyk-iac.yml` reusable workflow adds a Snyk Infrastructure-as-Code
scanning layer to a repository. It covers Terraform, Kubernetes manifests, and
Docker Compose files, uploading SARIF results to the Security tab for each
category independently. The workflow is opt-in and token-gated: when `SNYK_TOKEN`
is absent, all scan jobs no-op cleanly.

## What it runs

- `detect-iac` - checks for `SNYK_TOKEN` via env var and probes configured
  directories for .tf files, Kubernetes YAML, and Docker Compose files
- `snyk-terraform` - runs `snyk iac test` on `terraform-dirs`; uploads
  `iac-terraform.sarif` with category `snyk-iac-terraform`
- `snyk-kubernetes` - runs `snyk iac test` on `k8s-dirs`; uploads
  `iac-k8s.sarif` with category `snyk-iac-kubernetes`
- `snyk-compose` - runs `snyk iac test` on `compose-dirs`; uploads
  `iac-compose.sarif` with category `snyk-iac-compose`
- `snyk-iac-gate` - aggregates results with `if: always()`; treats `success`
  or `skipped` as passing; fails only when a scan job returned `failure`

## Minimal usage

```yaml
jobs:
  snyk-iac:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-snyk-iac.yml@v1
    permissions:
      contents: read
      security-events: write   # required for SARIF upload
    with:
      terraform-dirs: 'infra'
      fail-on-high: true
    secrets:
      SNYK_TOKEN: ${{ secrets.SNYK_TOKEN }}
```

## Inputs

| Input | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `terraform-dirs` | string | no | `.` | Space-separated directories to scan for Terraform (.tf) files; default scans repo root |
| `k8s-dirs` | string | no | `''` | Space-separated directories to scan for Kubernetes manifests; empty string skips this scanner |
| `compose-dirs` | string | no | `''` | Space-separated directories to scan for Docker Compose files; empty string skips this scanner |
| `fail-on-high` | boolean | no | `true` | Fail the build on HIGH/CRITICAL Snyk IaC findings |

## Secrets

| Secret | Required | Purpose |
|--------|----------|---------|
| `SNYK_TOKEN` | no | Snyk API token. When absent, all scan jobs no-op. |

## Caller permissions required

The caller must grant the following at the workflow or calling-job level:

- `contents: read`
- `security-events: write`

Omitting `security-events: write` causes a startup failure (`startup_failure` /
generic "workflow file issue") before any job runs, because a called workflow's
token is bounded by the caller's permissions.

## IaC detection behavior

The `detect-iac` job runs first and probes for IaC file presence before any
scan job starts. This is necessary because `snyk iac test` exits with code 2
(hard error) when passed a directory containing no supported files, which would
fail the build even when IaC scanning is legitimately not applicable.

Detection logic:

- For Terraform: searches up to 5 directory levels deep for any `*.tf` file in
  `terraform-dirs`
- For Kubernetes: searches for `*.yaml` or `*.yml` files in `k8s-dirs`
- For Compose: searches for `docker-compose*.yml` or `docker-compose*.yaml`
  in `compose-dirs`

A scan job only runs when its input directory is non-empty, `SNYK_TOKEN` is
present, AND the corresponding file type was detected.

The gate treats `skipped` as passing, so a repo with no Terraform files passes
the gate cleanly without operator intervention.

## Operator setup

1. **Create the Snyk account, org, and token.** Create a Snyk account, create
   one Snyk Organization (a CI token reports to its org regardless of repo
   owner, so one org covers both GitHub owners on Free), and generate a service
   token.

2. **Set the secret.** Mirror the existing `SONAR_TOKEN` pattern: an org-level
   secret for ByronWilliamsCPA and a repo-level secret for williaby personal
   repos.

   ```bash
   # ByronWilliamsCPA org repos (visibility: all)
   gh secret set SNYK_TOKEN --org ByronWilliamsCPA --visibility all

   # williaby personal repos
   ./scripts/sync-secrets.sh
   ```

3. **Identify IaC directories.** Map the directories that contain Terraform,
   Kubernetes, or Docker Compose files. Pass each set as a space-separated
   string to the corresponding input. If a scanner type is not present in the
   repo, omit the input (the empty default skips it automatically).

## Example: homelab-infra (Terraform)

homelab-infra contains Terraform in `infra/`, Kubernetes manifests in `k8s/`,
and Docker Compose files in the repo root:

```yaml
jobs:
  snyk-iac:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-snyk-iac.yml@v1
    permissions:
      contents: read
      security-events: write
    with:
      terraform-dirs: 'infra'
      k8s-dirs: 'k8s'
      compose-dirs: '.'
      fail-on-high: true
    secrets:
      SNYK_TOKEN: ${{ secrets.SNYK_TOKEN }}
```

## Notes

- This workflow is independent of `python-standard-stack.yml`. Call it as a
  separate job alongside the standard stack; do not try to absorb it into the
  stack (most Python repos have no IaC files).
- Directory paths must not contain spaces (org policy; the workflow uses IFS
  word-splitting on space-separated inputs).
- Multi-directory input example: `terraform-dirs: 'infra modules'` scans both
  `infra/` and `modules/` in one job.
- The self-test in `.github/workflows/self-test.yml` points `terraform-dirs`
  at `scripts/` (which has no .tf files); this exercises the no-op detection
  path on every PR.
- SARIF results appear in the repository's Security tab under Code Scanning.
  Each scanner uploads with its own category (`snyk-iac-terraform`,
  `snyk-iac-kubernetes`, `snyk-iac-compose`), so they do not overwrite each
  other.

See [ADR-003](../planning/adr/adr-003-snyk-ai-code-security.md) for the IaC
scanning decision.
