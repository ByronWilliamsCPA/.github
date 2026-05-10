# Changelog

All notable changes to this project's shared workflow templates are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

This project uses date-based version headers (e.g. `[2025-01-07]`) rather than
semver because it is a shared workflow library with continuous deployment; there
are no numbered releases.

## [Unreleased]

### Added

- `python-precommit.yml`: new reusable workflow that runs `pre-commit run --all-files` in the project virtualenv via `uv run`; inputs `config-path`, `python-version`, `fail-fast`; all inputs via env vars; SHA-pinned actions
- `python-standard-stack.yml`: new composite reusable workflow chaining `python-ci.yml`, `python-security-analysis.yml`, and `python-sbom.yml` via `needs:`; recommended quickstart for new repos; exposes `python-version`, `source-directory`, `coverage-threshold`, `fail-on-high`; optional `SONAR_TOKEN`/`CODECOV_TOKEN` passthroughs
- `python-supplemental-checks.yml`: `enable-commit-lint` input (default false) that validates PR titles against Conventional Commits format via SHA-pinned `amannn/action-semantic-pull-request`; commit-lint status added to supplemental summary
- `python-scorecard.yml`: `min-score` input (type: number, default 0 = gate disabled) and `Evaluate Scorecard Scores` step that parses SARIF output and fails CI if any of Branch-Protection, Code-Review, Dangerous-Workflow, Token-Permissions, or Pinned-Dependencies scores below the threshold
- `scripts/update-pinned-actions.sh`: developer tool to scan workflow files for outdated pinned action SHAs and propose or apply updates within the same major version
- `CHANGELOG.md`: required OpenSSF baseline file
- Actionlint static analysis for GitHub Actions workflows via `.qlty/qlty.toml`
- `.yamllint` configuration file for YAML style enforcement
- `tests/update-pinned-actions.bats`: 38 automated tests covering dry-run, apply mode, annotated tag resolution, and sandbox PATH validation for the action-pinning script
- `tests/libs/bats-core`, `tests/libs/bats-support`, `tests/libs/bats-assert` submodules for test infrastructure
- `.github/workflows/shell-tests.yml`: CI workflow that runs bats tests on pushes and pull requests touching `scripts/`, `tests/`, or the workflow file itself

### Changed

- `python-ci.yml`: remove `check-secrets` job, `sonarcloud-quality-gate` job, and 7 Codecov upload/analytics steps; use `python-sonarcloud.yml` and `python-codecov.yml` directly for those integrations
- `python-ci.yml`: replace `safety` with `uvx`-free `uv run pip-audit` for dependency vulnerability scanning (CLAUDE.md standard); add `-c pyproject.toml` flag to bandit
- `python-ci.yml`: simplify `ci-gate` from 5-job to 3-job dependency (`quality-checks`, `llm-governance`, `matrix-testing`)
- `python-supplemental-checks.yml`: replace PR-title string parsing for major/minor/patch classification with label-based detection (`major`, `minor`, `patch`, `semver:*`, `version-update:semver-*` labels) -- not spoofable via title text
- `python-pr-validation.yml`: replace 7-job implementation with single hard-fail migration stub; callers must migrate to `python-ci.yml` and `python-supplemental-checks.yml` (breaking change)
- Rename `ci-summary` to `CI Gate` in `python-ci.yml`; upgrade from passive summary to active gate that fails when required upstream jobs (`quality-checks`, `llm-governance`) fail or are cancelled; optional jobs (`sonarcloud-quality-gate`, `matrix-testing`) pass when skipped
- Rename `Security Gate` to `Security Gate Validation` in `python-security-analysis.yml` to match CI-015 branch protection context
- Rename `Validation Summary` to `Dependency & Standards Validation` in `python-pr-validation.yml` to match CI-016 branch protection context
- Align `workflow-templates/python-security-analysis.yml` job display names with renamed check context
- Replace em-dash with semicolon in `SUPPORT.md`
- Prose cleanup across 18 documentation files to remove AI-pattern language and improve plain-language clarity

### Fixed

- `python-scorecard.yml`: hard-code `publish_results: false` in the `ossf/scorecard-action` step and remove `id-token: write` from the workflow permissions; the OIDC token `repository` claim resolves to the `.github` org repo when the workflow runs as a reusable callee, causing scorecard-action to publish to the wrong repository and error; the `publish-results` input is retained for backwards compatibility but is now deprecated and always treated as false; SARIF upload to the Security tab is unaffected
- `scorecard.yml`: remove `publish-results: true` and `id-token: write` from the `.github` org repo's own scorecard caller to align with the reusable workflow fix
- `python-publish-pypi.yml`: replace `uv run pip-audit` / `uv run bandit` with `uv run --with` invocations that pin tool versions (`pip-audit==2.10.0`, `bandit[toml]==1.9.4`); the previous form required both tools to be listed as project dev dependencies in every downstream caller's `uv.lock`, silently failing or auditing an empty environment when they were absent
- Fix stale `williaby` org reference in usage example comments for `python-fuzzing.yml`, `python-performance-regression.yml`, and `python-qlty-coverage.yml`
- Add `timeout-minutes: 5` to `build-matrix` and `compatibility-summary` jobs in `python-compatibility.yml`
- Add `timeout-minutes: 5` to `check-configuration` jobs in `python-sonarcloud.yml` and `python-qlty-coverage.yml`
- `scripts/update-pinned-actions.sh`: `usage()` function now exits with code 1 instead of 0 on invalid usage

### Security

- Fix script injection vulnerability in `python-codecov.yml`: move `inputs.coverage-files` to env var before shell use (SonarCloud S7630)
- Pin `slsa-framework/slsa-github-generator` to full commit SHA in `python-slsa.yml` (SonarCloud S7637)

## [2026-04-13]

### Fixed

- LLM governance: replace `fromJSON` with direct numeric comparison for `critical_tags`
- LLM governance: only block PRs on `#CRITICAL` tags; demote `#ASSUME` to warning
- Security: add `pull-requests: read` permission to detect-changes job
- CI: move `fromJSON` to outer level in matrix strategy ternary

## [2026-04-10]

### Changed

- Update action pins ahead of Node.js 20 deprecation deadlines

### Fixed

- SBOM: use exact filename for `upload-artifact` path
- SBOM: resolve `upload-artifact` path via `github.workspace` context
- SBOM: downgrade `upload-artifact` to v4.5.0 to fix glob resolver
- SBOM: anchor SBOM output path to `GITHUB_WORKSPACE`
- SBOM: repair silent generation failure in `python-sbom` workflow

## [2026-04-05]

### Added

- Trivy `.trivyignore` file support in container security workflow
- Harbor registry setup documentation

## [2025-11-23]

### Added

- Initial reusable workflow library for Python projects
- Workflows: CI, PR validation, coverage upload, SLSA provenance, SBOM, security analysis, SonarCloud, ScoreCard, release, publish to PyPI
- Shared community health files: SECURITY.md, CONTRIBUTING.md, SUPPORT.md, issue templates

[Unreleased]: https://github.com/ByronWilliamsCPA/.github/compare/2026-04-13...HEAD
[2026-04-13]: https://github.com/ByronWilliamsCPA/.github/compare/2026-04-10...2026-04-13
[2026-04-10]: https://github.com/ByronWilliamsCPA/.github/compare/2026-04-05...2026-04-10
[2026-04-05]: https://github.com/ByronWilliamsCPA/.github/compare/2025-11-23...2026-04-05
[2025-11-23]: https://github.com/ByronWilliamsCPA/.github/releases/tag/2025-11-23
