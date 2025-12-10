# Python PyPI Publishing Workflow

Reusable workflow for publishing Python packages to PyPI or TestPyPI using OIDC Trusted Publishing (no secrets needed).

## Quick Reference

**Workflow**: `.github/workflows/python-publish-pypi.yml`
**Type**: Reusable (`workflow_call`)
**Security**: OIDC Trusted Publishing (no API tokens)

## Features

- ✅ **OIDC Trusted Publishing** - No secrets or API tokens needed
- ✅ **Built-in Security Scanning** - Safety (dependencies) + Bandit (code)
- ✅ **Dual Publishing** - Support for PyPI and TestPyPI
- ✅ **Package Verification** - Twine checks before publishing
- ✅ **Security Hardening** - Step Security Harden Runner
- ✅ **Comprehensive Summaries** - Detailed GitHub step summaries

## Usage

### Basic Example

```yaml
name: Publish to PyPI

on:
  release:
    types: [published]

jobs:
  publish:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-publish-pypi.yml@main
    with:
      package-name: 'my-package'
    permissions:
      id-token: write
      contents: read
```

### With Manual Trigger (TestPyPI Support)

```yaml
name: Publish to PyPI

on:
  release:
    types: [published]
  workflow_dispatch:
    inputs:
      use_testpypi:
        description: 'Publish to TestPyPI instead of PyPI'
        type: boolean
        default: false

jobs:
  publish:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-publish-pypi.yml@main
    with:
      package-name: 'my-package'
      use-testpypi: ${{ inputs.use_testpypi || false }}
    permissions:
      id-token: write
      contents: read
```

### With Custom Configuration

```yaml
jobs:
  publish:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-publish-pypi.yml@main
    with:
      package-name: 'my-package'
      python-version: '3.11'
      source-directory: 'lib'
      run-security-checks: true
    permissions:
      id-token: write
      contents: read
```

## Inputs

| Input | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `package-name` | string | No | `'your-package'` | PyPI package name (for display in summaries) |
| `use-testpypi` | boolean | No | `false` | Publish to TestPyPI instead of PyPI |
| `python-version` | string | No | `'3.12'` | Python version for building packages |
| `run-security-checks` | boolean | No | `true` | Run Safety + Bandit before publishing |
| `source-directory` | string | No | `'src'` | Source directory for security scans |

## Outputs

None - Results displayed in GitHub Step Summary

## Required Permissions

```yaml
permissions:
  id-token: write    # Required for OIDC authentication with PyPI
  contents: read     # Required for checking out repository
```

## PyPI Setup (One-Time)

### 1. Configure PyPI Trusted Publisher

1. Go to [PyPI Trusted Publishers](https://pypi.org/manage/account/publishing/)
2. Click "Add a new publisher"
3. Fill in:
   - **PyPI Project Name**: `your-package-name`
   - **Owner**: `ByronWilliamsCPA` (or your GitHub org/username)
   - **Repository**: `your-repository-name`
   - **Workflow**: `publish-pypi.yml` (your caller workflow filename)
   - **Environment**: Leave blank (or use `release` if you add environment protection)

### 2. Configure TestPyPI (Optional, for testing)

1. Go to [TestPyPI Trusted Publishers](https://test.pypi.org/manage/account/publishing/)
2. Add same configuration as PyPI

**⚠️ Important**: The workflow filename must match your **caller workflow** (in your repo), not the reusable workflow path.

## Testing

### Test with TestPyPI

```bash
# Manual workflow trigger
gh workflow run publish-pypi.yml --field use_testpypi=true

# Check workflow status
gh run list --workflow=publish-pypi.yml

# View workflow logs
gh run view --log
```

### Verify Publication

**TestPyPI**:
```bash
# Check package page
open https://test.pypi.org/project/your-package-name/

# Test installation
pip install --index-url https://test.pypi.org/simple/ your-package-name
```

**Production PyPI**:
```bash
# Check package page
open https://pypi.org/project/your-package-name/

# Test installation
pip install your-package-name
```

## Production Release

### Create Release

```bash
# Create and push tag
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0

# Create GitHub release
gh release create v1.0.0 --generate-notes
```

The workflow automatically triggers on release creation and publishes to PyPI.

## Security Scanning

When `run-security-checks: true` (default), the workflow runs:

### 1. Safety - Dependency Vulnerability Scanning

Checks dependencies against known vulnerability databases:
- CVE databases
- GitHub Security Advisories
- Python Package Index (PyPI) advisories

**Example findings**:
```
╒══════════════════════════════════════════════════════════════════════════════╕
│                                                                              │
│                               /$$$$$$            /$$                         │
│                              /$$__  $$          | $$                         │
│           /$$$$$$$  /$$$$$$ | $$  \__//$$$$$$  /$$$$$$   /$$   /$$           │
│          /$$_____/ |____  $$| $$$$   /$$__  $$|_  $$_/  | $$  | $$           │
│         |  $$$$$$   /$$$$$$$| $$_/  | $$$$$$$$  | $$    | $$  | $$           │
│          \____  $$ /$$__  $$| $$    | $$_____/  | $$ /$$| $$  | $$           │
│          /$$$$$$$/|  $$$$$$$| $$    |  $$$$$$$  |  $$$$/|  $$$$$$$           │
│         |_______/  \_______/|__/     \_______/   \___/   \____  $$           │
│                                                          /$$  | $$           │
│                                                         |  $$$$$$/           │
│  by safetycli.com                                        \______/            │
│                                                                              │
╘══════════════════════════════════════════════════════════════════════════════╛
```

### 2. Bandit - Code Security Scanning

Scans Python source code for:
- Hardcoded passwords/secrets
- SQL injection vulnerabilities
- Insecure deserialization
- Shell injection risks
- Unsafe YAML/pickle usage
- Weak cryptography

**⚠️ Important**: Security checks produce **warnings only** - they don't block publishing. Review findings before releasing!

### Disable Security Checks

```yaml
with:
  run-security-checks: false  # Not recommended for production
```

## Workflow Steps

### Build Job
1. **Harden Runner** - Audit egress network calls
2. **Checkout** - Fetch repository code
3. **Setup Python** - Install specified Python version
4. **Install UV** - Install UV package manager
5. **Security Checks** - Run Safety + Bandit (if enabled)
6. **Build** - Create wheel and sdist packages
7. **Verify** - Run `twine check` on packages
8. **Upload** - Store artifacts for publishing

### Publish Jobs
- **publish-to-pypi** - Publishes to PyPI (if `use-testpypi: false`)
- **publish-to-testpypi** - Publishes to TestPyPI (if `use-testpypi: true`)

Both jobs:
1. **Harden Runner** - Audit egress network calls
2. **Download** - Retrieve build artifacts
3. **Verify** - List packages to publish
4. **Publish** - Upload to PyPI/TestPyPI using OIDC
5. **Summary** - Display installation instructions

## Troubleshooting

### OIDC Token Verification Failed

**Symptoms**:
```
Error: OIDC token verification failed
```

**Solutions**:
1. Verify PyPI Trusted Publisher uses **caller workflow name** (not reusable workflow path)
2. Check repository owner matches PyPI configuration
3. Ensure `permissions: id-token: write` in caller workflow
4. Confirm workflow runs from correct branch/repository

### No Files Found in dist/

**Symptoms**:
```
Error: No files found in dist/
```

**Solutions**:
1. Check `pyproject.toml` has correct package configuration
2. Verify `uv.lock` exists and is up to date
3. Review build logs for errors
4. Ensure package structure is correct (src layout recommended)

### Security Check Warnings

**Symptoms**:
```
⚠️  Safety check found issues - review before publishing
⚠️  Bandit found issues - review before publishing
```

**Expected Behavior**: Security checks produce warnings only, they don't block publishing.

**Action**:
1. Review security findings in workflow logs
2. Address critical vulnerabilities before production release
3. Consider using TestPyPI for risky packages
4. Document any accepted risks

### Package Already Exists

**Symptoms**:
```
Error: File already exists
```

**Solutions**:
1. Increment version in `pyproject.toml`
2. Delete release and tag, recreate with new version
3. Use TestPyPI for version testing

## Migration from Standalone Workflow

See [PyPI Publishing Migration Guide](../migration/pypi-publishing-migration.md) for complete instructions.

**Summary**:
1. Update PyPI Trusted Publisher configuration
2. Replace standalone workflow with caller workflow
3. Test with TestPyPI
4. Verify production release

## Examples

- [Complete Example](../../examples/publish-pypi-caller.yml) - Ready-to-use caller workflow
- [Migration Guide](../migration/pypi-publishing-migration.md) - Step-by-step migration instructions

## Additional Resources

- [PyPI Trusted Publishing Documentation](https://docs.pypi.org/trusted-publishers/)
- [GitHub OIDC Documentation](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect)
- [UV Package Manager](https://github.com/astral-sh/uv)
- [Twine Documentation](https://twine.readthedocs.io/)
