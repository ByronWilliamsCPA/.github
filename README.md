# Centralized Community Health Files

[![Contributor Covenant](https://img.shields.io/badge/Contributor%20Covenant-2.1-4baaaa.svg)](https://www.contributor-covenant.org/version/2/1/code_of_conduct/)

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

## Workflow Templates

The [`workflow-templates/`](./workflow-templates/) directory contains reusable GitHub Actions workflows for Python projects:

- **Python CI Pipeline** - Comprehensive CI with UV, pytest, MyPy, and Ruff
- **Codecov Upload** - Secure coverage reporting workflow
- **Security Analysis** - CodeQL, Bandit, Safety, OSV Scanner, and OWASP checks
- **Documentation** - MkDocs build, validation, and GitHub Pages deployment
- **Release** - SLSA Level 3 provenance and Sigstore signing
- **Publish to PyPI** - OIDC Trusted Publishing for PyPI/TestPyPI
- **Fuzz Testing** - ClusterFuzzLite integration
- **SonarCloud** - Continuous code quality monitoring

See the [workflow-templates README](./workflow-templates/README.md) for detailed documentation.

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

_Last updated: November 16, 2025_  
