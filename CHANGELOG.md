# Changelog

All notable changes to this project's shared workflow templates are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- `scripts/update-pinned-actions.sh`: developer tool to scan workflow files for outdated pinned action SHAs and propose or apply updates within the same major version
- `CHANGELOG.md`: required OpenSSF baseline file
- Actionlint static analysis for GitHub Actions workflows via `.qlty/qlty.toml`
- `.yamllint` configuration file for YAML style enforcement
- `tests/update-pinned-actions.bats`: 38 automated tests covering dry-run, apply mode, annotated tag resolution, and sandbox PATH validation for the action-pinning script
- `tests/libs/bats-core`, `tests/libs/bats-support`, `tests/libs/bats-assert` submodules for test infrastructure
- `.github/workflows/shell-tests.yml`: CI workflow that runs bats tests on pushes and pull requests touching `scripts/`, `tests/`, or the workflow file itself

### Changed

- Rename `ci-summary` to `CI Gate` in `python-ci.yml`; upgrade from passive summary to active gate that fails when required upstream jobs (`quality-checks`, `llm-governance`) fail or are cancelled; optional jobs (`sonarcloud-quality-gate`, `matrix-testing`) pass when skipped
- Rename `Security Gate` to `Security Gate Validation` in `python-security-analysis.yml` to match CI-015 branch protection context
- Rename `Validation Summary` to `Dependency & Standards Validation` in `python-pr-validation.yml` to match CI-016 branch protection context
- Align `workflow-templates/python-security-analysis.yml` job display names with renamed check context
- Replace em-dash with semicolon in `SUPPORT.md`
- Prose cleanup across 18 documentation files to remove AI-pattern language and improve plain-language clarity

### Fixed

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
