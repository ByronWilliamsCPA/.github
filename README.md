# Centralized Community Health Files

[![CI Status](https://github.com/ByronWilliamsCPA/.github/actions/workflows/shell-tests.yml/badge.svg?branch=main)](https://github.com/ByronWilliamsCPA/.github/actions/workflows/shell-tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Contributor Covenant](https://img.shields.io/badge/Contributor%20Covenant-2.1-4baaaa.svg)](https://www.contributor-covenant.org/version/2/1/code_of_conduct/)
[![GitHub last commit](https://img.shields.io/github/last-commit/ByronWilliamsCPA/.github/main)](https://github.com/ByronWilliamsCPA/.github/commits/main)

This repository serves two purposes for the `ByronWilliamsCPA` GitHub organization: it provides shared community-health files that automatically apply to all public repositories, and it hosts centralized reusable GitHub Actions workflows for Python projects. Both live here to keep org-level governance in one place.

## Included Files

- [`CODE_OF_CONDUCT.md`](./CODE_OF_CONDUCT.md)  
  Defines expected contributor behavior and enforcement procedures.

- [`SECURITY.md`](./SECURITY.md)  
  Describes our vulnerability-reporting process, supported versions, and
- response timelines.

- [`CONTRIBUTING.md`](./CONTRIBUTING.md)  
  Guides contributors through issue filing, pull-request workflow, DCO sign-off,
   and local setup.

- [`SUPPORT.md`](./SUPPORT.md)  
  Outlines support channels, prerequisites, SLAs, and community contributions.

- [`GOVERNANCE.md`](./GOVERNANCE.md)  
  Describes project roles, decision-making processes, and how governance can evolve.

- [`CODEOWNERS`](./CODEOWNERS)  
  Assigns default and path-specific code owners organization-wide.

- [`FUNDING.yml`](./FUNDING.yml)  
  Indicates our solo-practitioner stance and points to non-financial
  contribution paths.

- `.github/ISSUE_TEMPLATE/bug.yml`
  Structured template for filing bug reports.

- `.github/ISSUE_TEMPLATE/feature.yml`
  Structured template for proposing new features.

- `.github/ISSUE_TEMPLATE/config.yml`
  Configuration for issue template chooser and external links.

- [`pull_request_template.md`](./pull_request_template.md)
  Standard template for pull request descriptions.

- [`dependabot.yml`](./dependabot.yml)
  Automated dependency update configuration for multiple ecosystems.

- [`LICENSE`](./LICENSE)
  MIT License for organization projects.

## Reusable Workflows

The `.github/workflows/` directory contains centralized, reusable GitHub Actions workflows that can be called from any Python repository. Most workflows are zero-config or lightly configured via inputs. A few -- SonarCloud, Qlty Coverage, and Fuzzing -- require an account and project setup on the respective platform before use.

### Prerequisites

Calling repos must provide:

- `pyproject.toml` at the repo root -- used by Ruff, BasedPyright, pytest, and coverage tools to read project configuration
- A `[tool.pytest.ini_options]` section (or equivalent `pytest.ini`) with `testpaths` configured
- Any workflow-specific secrets set at the org or repo level:

| Workflow | Required secret(s) |
| --- | --- |
| Python CI | `CODECOV_TOKEN` (optional, for coverage upload) |
| SonarCloud | `SONAR_TOKEN` + external SonarCloud project setup |
| OpenSSF Scorecard | `SCORECARD_TOKEN` (for scheduled publish runs) |
| PyPI Publishing | None -- uses OIDC trusted publishing |
| Qlty Coverage | `QLTY_COVERAGE_TOKEN` + `qlty.toml` in calling repo |

### Available Workflows

- **[Python CI](USAGE_EXAMPLES.md#python-ci)** (`python-ci.yml`) - Comprehensive CI with testing, linting, type checking across multiple Python versions
- **[PyPI Publishing](USAGE_EXAMPLES.md#pypi-publishing)** (`python-publish-pypi.yml`) - OIDC-authenticated publishing (no secrets!)
- **[Security Analysis](USAGE_EXAMPLES.md#security-analysis)** (`python-security-analysis.yml`) - CodeQL, Bandit, Safety, OSV Scanner
- **[Fuzzing](docs/workflows/python-fuzzing.md)** (`python-fuzzing.yml`) - ClusterFuzzLite continuous fuzzing for security vulnerabilities
- **[Performance Regression](docs/workflows/python-performance-regression.md)** (`python-performance-regression.yml`) - Automated performance testing with baseline comparison
- **[SonarCloud](docs/workflows/python-sonarcloud.md)** (`python-sonarcloud.yml`) - Code quality and security analysis with SonarCloud
- **[Qlty Coverage](docs/workflows/python-qlty-coverage.md)** (`python-qlty-coverage.yml`) - Coverage tracking with Qlty Cloud
- **[Documentation](USAGE_EXAMPLES.md#documentation)** (`python-docs.yml`) - MkDocs build and GitHub Pages deployment
- **[Releases](USAGE_EXAMPLES.md#releases)** (`python-release.yml`) - Signed releases with SLSA provenance and SBOM
- **[Codecov Coverage Upload](.github/workflows/python-codecov.yml)** (`python-codecov.yml`) - Securely uploads coverage reports to Codecov without re-running tests
- **[Compatibility Testing](.github/workflows/python-compatibility.yml)** (`python-compatibility.yml`) - Matrix testing across Python versions and operating systems
- **[Container Security](.github/workflows/python-container-security.yml)** (`python-container-security.yml`) - Trivy container image scanning and Hadolint Dockerfile linting
- **[Docker Build](.github/workflows/python-docker.yml)** (`python-docker.yml`) - Multi-platform Docker image builds with GHCR publishing
- **[FIPS Compatibility](docs/workflows/python-fips-compatibility.md)** (`python-fips-compatibility.yml`) - FIPS 140-2/140-3 compliance checks for code and dependencies
- **[Mutation Testing](.github/workflows/python-mutation.yml)** (`python-mutation.yml`) - Validates test suite effectiveness using mutmut mutation testing
- **[REUSE Compliance](.github/workflows/python-reuse.yml)** (`python-reuse.yml`) - FSFE REUSE 3.0 license and copyright compliance
- **[SBOM](.github/workflows/python-sbom.yml)** (`python-sbom.yml`) - Software Bill of Materials generation and dependency vulnerability scanning
- **[OpenSSF Scorecard](.github/workflows/python-scorecard.yml)** (`python-scorecard.yml`) - Repository security health scoring via OpenSSF Scorecard
- **[Supplemental Checks](.github/workflows/python-supplemental-checks.yml)** (`python-supplemental-checks.yml`) - Optional PR checks including link validation and changelog enforcement

### Key Features

✅ **Security Hardened** - All actions pinned to commit SHAs
✅ **Minimal Permissions** - Principle of least privilege
✅ **Network Monitoring** - harden-runner on all jobs
✅ **OIDC Authentication** - No stored secrets for PyPI
✅ **Customizable** - Extensive input parameters
✅ **Qlty Integration** - Automated code quality checks (see below)

### Quick Start

```yaml
# .github/workflows/ci.yml in your Python repo
name: CI
on: [push, pull_request]

jobs:
  ci:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-ci.yml@main
    with:
      python-versions: '["3.11", "3.12"]'
    secrets:
      CODECOV_TOKEN: ${{ secrets.CODECOV_TOKEN }}
```

### Documentation

- **[USAGE_EXAMPLES.md](USAGE_EXAMPLES.md)** - Detailed usage examples
- **[CONVERSION_ACTION_PLAN.md](CONVERSION_ACTION_PLAN.md)** - Step-by-step guide for migrating a repo from standalone workflow definitions to these centralized ones
- **[ACTION_SHA_REFERENCE.md](ACTION_SHA_REFERENCE.md)** - Action commit SHAs
- **[QLTY_INTEGRATION.md](QLTY_INTEGRATION.md)** - Qlty Cloud integration guide
- **[PYPI_WORKFLOW_ANALYSIS.md](PYPI_WORKFLOW_ANALYSIS.md)** - PyPI workflow analysis & migration
- **[docs/workflows/](docs/workflows/)** - Workflow-specific documentation
- **[docs/migration/](docs/migration/)** - Step-by-step migration guides
- **[examples/](examples/)** - Ready-to-use workflow examples

---

## Qlty Cloud Integration

Qlty Cloud provides centralized code quality management across all repositories. See [QLTY_INTEGRATION.md](QLTY_INTEGRATION.md) for setup guide.

## How It Works

All of these files live in the `.github/` directory at the **organization**
level, so they automatically apply to every public repository (unless
overridden by a repo-specific copy).

## Getting Started

**To use the reusable workflows in your Python project**, reference them directly by name -- no fork or clone needed:

```yaml
uses: ByronWilliamsCPA/.github/.github/workflows/python-ci.yml@main
```

See [USAGE_EXAMPLES.md](USAGE_EXAMPLES.md) for full examples and all available input parameters. See the [Prerequisites](#prerequisites) section above for what your repo must provide.

**To override a community health file** for a specific repo, copy the relevant file into that repo’s root or `.github/` folder. GitHub uses the repo-level copy when one exists.

**To improve or extend the workflow templates or community health files**, open a pull request against this repository. Merged changes apply org-wide automatically.

_Last updated: April 30, 2026_  
