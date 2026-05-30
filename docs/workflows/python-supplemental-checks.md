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
| `link-check-paths` | string | no | `./docs/**/*.md ./README.md ./CONTRIBUTING.md` | Paths to check for broken links (space-separated) |
| `link-check-fail` | boolean | no | `false` | Fail workflow on broken links |
| `link-check-exclude-patterns` | string | no | GitHub/Linear URL patterns | Regex patterns to exclude from link checking (comma-separated) |
| `enable-changelog-check` | boolean | no | `false` | Require CHANGELOG update on PRs |
| `changelog-path` | string | no | `CHANGELOG.md` | Path to CHANGELOG file |
| `changelog-skip-labels` | string | no | `skip-changelog,dependencies,documentation` | PR labels that skip the changelog requirement (comma-separated) |
| `enable-cruft-check` | boolean | no | `false` | Enable cruft template synchronization check |
| `cruft-fail-on-diff` | boolean | no | `true` | Fail if project is out of sync with template |
| `python-version` | string | no | `3.12` | Python version for cruft check |
| `enable-automerge` | boolean | no | `false` | Enable auto-merge for Dependabot/Renovate PRs |
| `automerge-allowed-actors` | string | no | `dependabot[bot],renovate[bot]` | Bot usernames allowed for auto-merge (comma-separated) |
| `automerge-allowed-update-types` | string | no | `patch,minor` | Update types to auto-merge (comma-separated: patch,minor,major) |
| `automerge-merge-method` | string | no | `squash` | Merge method for auto-merge (merge, squash, rebase) |
| `enable-commit-lint` | boolean | no | `false` | Validate PR title format (Conventional Commits) |

## Usage

```yaml
jobs:
  supplemental:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-supplemental-checks.yml@v1
    with:
      enable-link-check: true
      enable-changelog-check: true
      changelog-skip-labels: skip-changelog,dependencies
```
