# python-supplemental-checks.yml -- Supplemental Quality Checks

A collection of optional quality checks not included in the standard CI stack.
Each check is disabled by default; enable only what your project needs.

## Available checks

| Check | Enable input | Description |
|-------|-------------|-------------|
| Link checking | `enable-link-check` | Checks documentation for broken URLs |
| Changelog enforcement | `enable-changelog-check` | **Deprecated, no-op.** Use `enable-commit-lint` plus `semantic-release: true` at release instead (see below) |
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
| `enable-changelog-check` | boolean | no | `false` | **Deprecated (no-op).** Enabling it only emits a deprecation warning; per-PR CHANGELOG edits are no longer required. Use `enable-commit-lint` plus `semantic-release: true` at release instead |
| `changelog-path` | string | no | `CHANGELOG.md` | Path to CHANGELOG file (retained for compatibility; the changelog check is a deprecated no-op) |
| `changelog-skip-labels` | string | no | `skip-changelog,dependencies,documentation` | PR labels that skip the changelog requirement, comma-separated (retained for compatibility; the changelog check is a deprecated no-op) |
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
    uses: ByronWilliamsCPA/.github/.github/workflows/python-supplemental-checks.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    with:
      enable-link-check: true
      # enable-changelog-check is deprecated (no-op); validate commit/PR titles
      # instead so the release can build the changelog automatically.
      enable-commit-lint: true
```

## Changelog: migrating off `enable-changelog-check`

`enable-changelog-check` previously required every PR to edit `CHANGELOG.md`.
Because the org merge queue stacks PRs speculatively, every PR editing the same
file caused textual conflicts, so only one PR could sit in the queue at a time.

The changelog is now generated at release time by
[python-semantic-release](https://python-semantic-release.readthedocs.io/) from
Conventional Commits, so the per-PR edit is redundant. To migrate:

1. Set `enable-commit-lint: true` here so PR titles are validated as
   Conventional Commits.
2. Set `semantic-release: true` in your release job so the changelog is built
   from those commits at release.
3. Drop `enable-changelog-check` from this workflow's inputs.

`enable-changelog-check`, `changelog-path`, and `changelog-skip-labels` are
retained for backward compatibility and take no effect beyond a deprecation
warning.
