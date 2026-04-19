# Changelog

All notable changes to this project's shared workflow templates are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Security
- Fix script injection vulnerability in `python-codecov.yml`: move `inputs.coverage-files` to env var before shell use (SonarCloud S7630)
- Pin `slsa-framework/slsa-github-generator` to full commit SHA in `python-slsa.yml` (SonarCloud S7637)

### Added
- `scripts/update-pinned-actions.sh`: developer tool to scan workflow files for outdated pinned action SHAs and propose or apply updates within the same major version
- `CHANGELOG.md`: required OpenSSF baseline file

### Changed
- Replace em-dash with semicolon in `SUPPORT.md`

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
