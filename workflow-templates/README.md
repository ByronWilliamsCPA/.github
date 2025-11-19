# Workflow Templates

This directory contains reusable GitHub Actions workflow templates for the williaby organization. These templates provide standardized CI/CD workflows for Python projects and can be easily added to any repository in the organization.

## Available Templates

### 1. Python CI Pipeline (`python-ci.yml`)
Comprehensive continuous integration workflow featuring:
- **UV dependency management** with optimized caching
- **Multi-version Python testing** (3.10-3.14)
- **MyPy type checking** with strict mode
- **Ruff linting and formatting**
- **Pytest** with 80%+ code coverage enforcement
- **Concurrent job execution** for faster CI

**Use when:** Setting up CI for any Python project

**Requirements:**
- `pyproject.toml` or `uv.lock`
- Test suite in `tests/` directory
- Python 3.10+ compatible code

---

### 2. Codecov Upload (`python-codecov.yml`)
Secure coverage reporting workflow:
- **Workflow_run trigger** to prevent pwn request vulnerabilities
- **Multi-version coverage** support (Python 3.10-3.14)
- **Automated Codecov uploads** with version-specific flags
- **GitHub Actions summary** with upload status

**Use when:** You want to track code coverage metrics with Codecov

**Requirements:**
- Codecov account and token configured in repository secrets
- CI workflow that generates `coverage.xml` artifacts

---

### 3. Security Analysis (`python-security-analysis.yml`)
Comprehensive security scanning suite:
- **CodeQL analysis** with security-extended queries
- **Bandit** for Python-specific security issues
- **Safety** for dependency vulnerability scanning
- **OSV Scanner** for known vulnerabilities
- **OWASP Dependency Check** with SARIF reporting
- **Dependency Review** on pull requests
- **Smart change detection** to optimize scan execution

**Use when:** Implementing security scanning for Python projects

**Requirements:**
- Python dependencies declared in `pyproject.toml` or `poetry.lock`
- CodeQL compatible Python code

---

### 4. Documentation with MkDocs (`python-docs.yml`)
Documentation build and deployment workflow:
- **MkDocs** static site generation
- **Docstring enforcement** with interrogate
- **Link validation** using Lychee
- **Markdown linting** with automatic fixes
- **GitHub Pages deployment** on main branch
- **PR preview builds**

**Use when:** Building project documentation with MkDocs

**Requirements:**
- `mkdocs.yml` configuration file
- Documentation in `docs/` directory
- GitHub Pages enabled in repository settings

---

### 5. Release with SLSA Provenance (`python-release.yml`)
Secure release automation workflow:
- **SLSA Level 3 provenance** attestations
- **Sigstore/Cosign keyless signing**
- **SBOM generation** in CycloneDX format
- **Artifact hashing** for integrity verification
- **Automated GitHub Releases** with verification instructions

**Use when:** Creating secure, verifiable Python package releases

**Requirements:**
- Semantic version tags (e.g., `v1.0.0`)
- `pyproject.toml` or `setup.py`
- UV or Poetry for building distributions

---

### 6. Publish to PyPI (`python-publish-pypi.yml`)
PyPI publishing workflow with modern security:
- **OIDC Trusted Publishing** (no API tokens needed)
- **TestPyPI support** for testing releases
- **Automatic** publishing on releases
- **Manual trigger** with TestPyPI option
- **Metadata validation** with Twine

**Use when:** Publishing Python packages to PyPI

**Requirements:**
- PyPI/TestPyPI account with Trusted Publishing configured
- `pyproject.toml` or `setup.py`
- Valid package metadata

**Setup Instructions:**
1. Go to PyPI account settings
2. Add a "pending" publisher with:
   - Repository: `owner/repo-name`
   - Workflow: `publish-pypi.yml`
   - Environment: (leave blank or use `release`)

---

### 7. Fuzz Testing (`python-cifuzzy.yml`)
Automated fuzzing with ClusterFuzzLite:
- **Google ClusterFuzzLite** integration
- **AddressSanitizer** for memory issue detection
- **SARIF reporting** to GitHub Security tab
- **Crash artifact preservation**
- **600-second fuzzing campaigns**

**Use when:** Testing input validators, parsers, or file handlers

**Requirements:**
- Fuzz test functions in your codebase
- Compatible with ClusterFuzzLite

---

### 8. SonarCloud Analysis (`python-sonarcloud.yml`)
Continuous code quality monitoring:
- **Bug detection** and code smell identification
- **Security vulnerability scanning**
- **Code coverage tracking**
- **Quality gate enforcement**
- **PR decoration** with inline comments
- **Technical debt metrics**

**Use when:** Monitoring code quality metrics with SonarCloud

**Requirements:**
- SonarCloud account
- `SONAR_TOKEN` secret configured in repository
- `SONAR_ORGANIZATION` and `SONAR_PROJECT_KEY` in workflow

---

## How to Use These Templates

### Option 1: Through GitHub UI
1. In your repository, click **Actions**
2. Click **New workflow**
3. Look for templates from your organization
4. Select the desired template and customize if needed

### Option 2: Manual Copy
1. Copy the desired `.yml` file from this directory
2. Create `.github/workflows/` in your repository
3. Paste the file and customize as needed
4. Commit and push to your repository

## Customization Guide

Most templates support these common customizations:

### Python Version
```yaml
python-version: '3.12'  # Change to your preferred version
```

### Coverage Thresholds
```yaml
pytest --cov --cov-report=xml --cov-fail-under=80  # Adjust percentage
```

### Branch Triggers
```yaml
on:
  pull_request:
    branches:
      - main          # Add or remove branches
      - develop
      - 'feature/**'
```

### Secrets Required

Different templates require different secrets:

| Template | Required Secrets | Optional Secrets |
|----------|------------------|------------------|
| CI | None | None |
| Codecov | `CODECOV_TOKEN` | None |
| Security Analysis | None | None (uses GITHUB_TOKEN) |
| Docs | None | `GITHUB_TOKEN` (auto-provided) |
| Release | None | `GITHUB_TOKEN` (auto-provided) |
| PyPI Publish | None (uses OIDC) | `PYPI_API_TOKEN` (legacy) |
| Fuzzing | None | None |
| SonarCloud | `SONAR_TOKEN` | None |

## Best Practices

1. **Start with CI** - Always begin with `python-ci.yml` as your foundation
2. **Add Security Early** - Include `python-security-analysis.yml` from the start
3. **Incremental Adoption** - Add templates one at a time to understand their impact
4. **Customize Sparingly** - Templates are designed to work out-of-the-box; only customize when necessary
5. **Keep Updated** - These templates receive updates; consider syncing periodically

## Template Maintenance

These templates are maintained centrally in the organization's `.github` repository. To suggest improvements:

1. Open an issue in `williaby/.github`
2. Describe the enhancement or fix needed
3. Include example use case if applicable

## Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Creating Workflow Templates](https://docs.github.com/en/actions/how-tos/reuse-automations/create-workflow-templates)
- [UV Package Manager](https://github.com/astral-sh/uv)
- [SLSA Framework](https://slsa.dev/)
- [Sigstore](https://www.sigstore.dev/)

---

_Last updated: November 16, 2025_
