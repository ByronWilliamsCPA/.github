# Centralized Community Health Files

[![CI Status](https://github.com/williaby/.github/actions/workflows/python-ci.yml/badge.svg?branch=main)](https://github.com/williaby/.github/actions/workflows/python-ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Contributor Covenant](https://img.shields.io/badge/Contributor%20Covenant-2.1-4baaaa.svg)](https://www.contributor-covenant.org/version/2/1/code_of_conduct/)
[![GitHub last commit](https://img.shields.io/github/last-commit/williaby/.github/main)](https://github.com/williaby/.github/commits/main)

This repository contains shared community-health files that apply
organization-wide across all public repositories under the `williaby` GitHub
account. They ensure consistency, streamline onboarding,
and support best practices.

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

The `.github/workflows/` directory contains centralized, reusable GitHub Actions workflows that can be called from any Python repository:

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
    uses: williaby/.github/.github/workflows/python-ci.yml@main
    with:
      python-versions: '["3.11", "3.12"]'
    secrets:
      CODECOV_TOKEN: ${{ secrets.CODECOV_TOKEN }}
```

### Documentation

- **[USAGE_EXAMPLES.md](USAGE_EXAMPLES.md)** - Detailed usage examples
- **[CONVERSION_ACTION_PLAN.md](CONVERSION_ACTION_PLAN.md)** - Migration guide
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

1. **Fork & Clone** this repo if you need to customize any file for a
     specific project.  
2. Review each file to see how it applies to your repository.  
3. If you maintain a repository that needs specialized adjustments, copy the
    relevant file into your repo’s root or `.github/` folder and tailor it accordingly.

_Last updated: December 15, 2025_  
