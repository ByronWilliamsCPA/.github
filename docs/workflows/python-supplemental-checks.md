# python-supplemental-checks.yml -- Supplemental Quality Checks

A collection of optional quality checks not included in the standard CI stack.
Each check is disabled by default; enable only what your project needs.

## Available checks

| Check | Enable input | Description |
|-------|-------------|-------------|
| Link checking | `enable-link-check` | Checks documentation for broken URLs |
| Changelog enforcement | `enable-changelog-check` | Requires CHANGELOG update on PRs |
| Cruft sync | `enable-cruft-check` | Verifies project is in sync with template |
| Auto-merge | `enable-automerge` | Auto-merges Dependabot/Renovate PRs |
| Commit lint | `enable-commit-lint` | Validates Conventional Commits format |

## Inputs

| Input | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `enable-link-check` | boolean | no | `false` | Enable documentation link checking |
| `link-check-paths` | string | no | `./docs/**/*.md` | Paths to check |
| `enable-changelog-check` | boolean | no | `false` | Require CHANGELOG update on PRs |
| `changelog-skip-labels` | string | no | `skip-changelog` | PR labels that skip the requirement |
| `enable-automerge` | boolean | no | `false` | Enable auto-merge for bots |
| `automerge-allowed-update-types` | string | no | `patch,minor` | Update types to auto-merge |
| `enable-commit-lint` | boolean | no | `false` | Validate PR title format |
| `python-version` | string | no | `3.12` | Python version for cruft check |

## Usage

```yaml
jobs:
  supplemental:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-supplemental-checks.yml@main
    with:
      enable-link-check: true
      enable-changelog-check: true
      changelog-skip-labels: skip-changelog,dependencies
```
