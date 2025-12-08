# Migrating to Reusable PyPI Publishing Workflow

This guide shows how to migrate from standalone PyPI publishing workflows to the centralized org-level reusable workflow.

## Overview

The reusable workflow provides:
- ✅ Built-in security scanning (Safety + Bandit)
- ✅ Centralized maintenance and updates
- ✅ Consistent publishing behavior across all repos
- ✅ OIDC Trusted Publishing (no secrets needed)
- ✅ Configurable Python versions and source directories

## Before Migration

**Standalone workflow in your repository** (e.g., `.github/workflows/publish-pypi.yml`):

```yaml
name: Publish to PyPI

on:
  release:
    types: [published]
  workflow_dispatch:
    inputs:
      use_testpypi:
        description: 'Publish to TestPyPI instead of PyPI'
        required: false
        default: true
        type: boolean

permissions: read-all

jobs:
  build:
    name: Build Distribution Packages
    runs-on: ubuntu-latest
    # ... build steps ...

  publish-to-pypi:
    name: Publish to PyPI
    needs: [build]
    # ... publishing steps ...
```

## After Migration

**Caller workflow** (minimal boilerplate):

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
        required: false
        default: false

jobs:
  publish:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-publish-pypi.yml@main
    with:
      package-name: 'image-preprocessing-detector'  # Your package name
      use-testpypi: ${{ inputs.use_testpypi || false }}
      python-version: '3.12'
      run-security-checks: true
      source-directory: 'src'
    permissions:
      id-token: write    # Required for OIDC
      contents: read
```

## Migration Steps

### Step 1: Update PyPI Trusted Publisher Configuration

1. Go to [PyPI Trusted Publishers](https://pypi.org/manage/account/publishing/)
2. **Update existing publisher** (or add new):
   - **PyPI Project Name**: `your-package-name`
   - **Owner**: `ByronWilliamsCPA` (or your org)
   - **Repository**: `your-repo-name`
   - **Workflow**: `publish-pypi.yml` (or your workflow name)
   - **Environment**: Leave blank (or use `release` if you add environment protection)

3. For TestPyPI: [TestPyPI Trusted Publishers](https://test.pypi.org/manage/account/publishing/)

**⚠️ Important**: The workflow path in PyPI configuration must match your **caller workflow name**, not the reusable workflow path.

### Step 2: Replace Standalone Workflow

Replace your existing `.github/workflows/publish-pypi.yml` with the caller workflow:

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
        required: false
        default: false

jobs:
  publish:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-publish-pypi.yml@main
    with:
      package-name: 'your-package-name'  # ← CHANGE THIS
      use-testpypi: ${{ inputs.use_testpypi || false }}
      python-version: '3.12'             # Optional: defaults to 3.12
      run-security-checks: true          # Optional: defaults to true
      source-directory: 'src'            # Optional: defaults to 'src'
    permissions:
      id-token: write
      contents: read
```

### Step 3: Test with TestPyPI

1. **Trigger manual workflow**:
   ```bash
   gh workflow run publish-pypi.yml --field use_testpypi=true
   ```

2. **Verify publication** at `https://test.pypi.org/project/your-package-name/`

3. **Test installation**:
   ```bash
   pip install --index-url https://test.pypi.org/simple/ your-package-name
   ```

### Step 4: Verify Production Release

1. Create a release tag:
   ```bash
   git tag -a v1.0.0 -m "Release v1.0.0"
   git push origin v1.0.0
   ```

2. Create GitHub release from tag

3. Workflow automatically publishes to PyPI

4. Verify at `https://pypi.org/project/your-package-name/`

## Configuration Options

### Required Inputs

None - all inputs have sensible defaults!

### Optional Inputs

| Input | Description | Default |
|-------|-------------|---------|
| `package-name` | PyPI package name (display only) | `'your-package'` |
| `use-testpypi` | Publish to TestPyPI instead | `false` |
| `python-version` | Python version for building | `'3.12'` |
| `run-security-checks` | Run Safety + Bandit before publish | `true` |
| `source-directory` | Source directory for security scans | `'src'` |

### Example: Custom Python Version

```yaml
jobs:
  publish:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-publish-pypi.yml@main
    with:
      package-name: 'my-package'
      python-version: '3.11'  # ← Use Python 3.11
    permissions:
      id-token: write
      contents: read
```

### Example: Disable Security Checks

```yaml
jobs:
  publish:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-publish-pypi.yml@main
    with:
      package-name: 'my-package'
      run-security-checks: false  # ← Skip security scans
    permissions:
      id-token: write
      contents: read
```

### Example: Non-standard Source Directory

```yaml
jobs:
  publish:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-publish-pypi.yml@main
    with:
      package-name: 'my-package'
      source-directory: 'lib'  # ← Scan lib/ instead of src/
    permissions:
      id-token: write
      contents: read
```

## Security Improvements

The reusable workflow adds **automatic security scanning** before publishing:

### 1. Dependency Vulnerability Scanning (Safety)

Checks all dependencies against known vulnerability databases:

```bash
safety check
```

**Example output**:
```
📦 Checking dependencies for vulnerabilities...
✓ No known security vulnerabilities found
```

### 2. Source Code Security Scanning (Bandit)

Scans Python source code for common security issues:

```bash
bandit -r src -ll
```

**Example issues detected**:
- Hardcoded passwords/secrets
- SQL injection vulnerabilities
- Insecure deserialization
- Unsafe YAML loading
- Shell injection risks

**⚠️ Important**: Security checks produce **warnings only** - they don't block publishing. Review findings before releasing!

## Troubleshooting

### Issue: "OIDC token verification failed"

**Cause**: PyPI Trusted Publisher configuration doesn't match workflow

**Solution**:
1. Check PyPI configuration uses **caller workflow name** (not reusable workflow path)
2. Verify repository owner matches
3. Ensure `permissions: id-token: write` is set in caller workflow

### Issue: "No files found in dist/"

**Cause**: Build failed or `uv build` didn't create packages

**Solution**:
1. Check build logs in workflow output
2. Verify `pyproject.toml` is correctly configured
3. Ensure `uv.lock` exists and is up to date

### Issue: Security checks fail but workflow continues

**Expected behavior** - Security checks produce warnings only and don't block publishing.

**Action required**: Review security findings in workflow logs before publishing to production.

## Benefits Summary

| Benefit | Description |
|---------|-------------|
| **Reduced boilerplate** | ~177 lines → ~20 lines in your workflow |
| **Automatic security** | Built-in Safety + Bandit scanning |
| **Centralized updates** | Update once in `.github`, all repos benefit |
| **Consistent behavior** | Same publishing logic across all projects |
| **OIDC security** | No secrets/tokens needed |
| **Audit trail** | Full publishing history at PyPI |

## Example: image_detection Migration

**Before** (177 lines in `.github/workflows/publish-pypi.yml`):
- Custom build job
- Custom publish-to-pypi job
- Custom publish-to-testpypi job
- No security scanning

**After** (20 lines in `.github/workflows/publish-pypi.yml`):

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
        required: false
        default: false

jobs:
  publish:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-publish-pypi.yml@main
    with:
      package-name: 'image-preprocessing-detector'
      use-testpypi: ${{ inputs.use_testpypi || false }}
    permissions:
      id-token: write
      contents: read
```

**Result**: Same functionality + security scanning, 89% less code!

## Next Steps

1. ✅ Update PyPI Trusted Publisher configuration
2. ✅ Replace standalone workflow with caller workflow
3. ✅ Test with TestPyPI
4. ✅ Verify production release
5. ✅ Delete old workflow file (optional - keep for reference)

## Additional Resources

- [PyPI Trusted Publishing Guide](https://docs.pypi.org/trusted-publishers/)
- [GitHub Actions Reusable Workflows](https://docs.github.com/en/actions/using-workflows/reusing-workflows)
- [OIDC Token Security](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect)
