# python-codecov.yml -- Coverage Upload

Uploads pytest coverage data to Codecov after a test run. Designed to run
as a separate job after the main CI job uploads a coverage artifact.

## Inputs

| Input | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `artifact-name` | string | no | `coverage-reports` | Name of the artifact containing coverage reports |
| `coverage-files` | string | no | `coverage*.xml` | Glob pattern for coverage XML files within artifact |
| `junit-files` | string | no | `junit-*.xml` | Glob pattern for JUnit XML files for Test Analytics |
| `flags` | string | no | | Codecov flags (comma-separated) |
| `name` | string | no | `coverage` | Name for the coverage upload |
| `fail-ci-if-error` | boolean | no | `false` | Fail the workflow if Codecov upload fails |
| `verbose` | boolean | no | `false` | Enable verbose output |
| `workflow-run-id` | string | no | | Workflow run ID to download artifacts from (for `workflow_run` trigger) |
| `commit-sha` | string | no | | Commit SHA override for `workflow_run` trigger; associates upload with the triggering commit |

## Secrets

| Secret | Required | Description |
|--------|----------|-------------|
| `CODECOV_TOKEN` | yes | Codecov upload token from codecov.io |

## Usage

```yaml
jobs:
  upload-coverage:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-codecov.yml@main
    secrets:
      CODECOV_TOKEN: ${{ secrets.CODECOV_TOKEN }}
```
