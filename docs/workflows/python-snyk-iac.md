# python-snyk-iac.yml -- Snyk IaC Scanning Layer

The `python-snyk-iac.yml` reusable workflow adds a Snyk Infrastructure-as-Code
scanning layer to a repository. It covers Terraform, Kubernetes manifests, and
Docker Compose files, publishing SARIF results as a workflow artifact for each
category independently. The workflow is opt-in and token-gated: when `SNYK_TOKEN`
is absent, all scan jobs no-op cleanly.

## What it runs

- `detect-iac` - checks for `SNYK_TOKEN` via env var and probes configured
  directories for .tf files, Kubernetes YAML, and Docker Compose files
- `snyk-terraform` - runs `snyk iac test` on `terraform-dirs`; publishes
  `iac-terraform.sarif` as the `snyk-iac-terraform-sarif` artifact
- `snyk-kubernetes` - runs `snyk iac test` on `k8s-dirs`; publishes
  `iac-k8s.sarif` as the `snyk-iac-kubernetes-sarif` artifact
- `snyk-compose` - runs `snyk iac test` on `compose-dirs`; publishes
  `iac-compose.sarif` as the `snyk-iac-compose-sarif` artifact
- `snyk-iac-gate` - aggregates results with `if: always()`; treats `success`
  or `skipped` as passing; fails only when a scan job returned `failure`

## Minimal usage

```yaml
jobs:
  snyk-iac:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-snyk-iac.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    permissions:
      contents: read
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

No elevated permissions are required; SARIF results are published as
workflow artifacts rather than uploaded to the Security tab (that path
required paid GitHub Advanced Security and has been removed).

## IaC detection behavior

The `detect-iac` job runs first and probes for IaC file presence before any
scan job starts. This is necessary because `snyk iac test` exits with code 2
(hard error) when passed a directory containing no supported files, which would
fail the build even when IaC scanning is legitimately not applicable.

Detection logic:

- For Terraform: searches up to 5 directory levels deep for any `*.tf` file in
  `terraform-dirs`
- For Kubernetes: searches up to 5 directory levels deep for `*.yaml` or `*.yml`
  files in `k8s-dirs`
- For Compose: searches up to 5 directory levels deep for all canonical Docker
  Compose v2 filenames (`compose.yaml`, `compose.yml`, `docker-compose*.yaml`,
  `docker-compose*.yml`) in `compose-dirs`

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
    uses: ByronWilliamsCPA/.github/.github/workflows/python-snyk-iac.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    permissions:
      contents: read
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
- SARIF results are published as workflow artifacts, one per scanner
  (`snyk-iac-terraform-sarif`, `snyk-iac-kubernetes-sarif`,
  `snyk-iac-compose-sarif`). Security tab upload was removed; that path
  required paid GitHub Advanced Security.

See [ADR-003](../architecture/adr-003-snyk-ai-code-security.md) for the IaC
scanning decision.
