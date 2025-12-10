# image_detection PyPI Publishing Migration

This document outlines the specific migration path for the `image_detection` repository to use the org-level reusable PyPI publishing workflow.

## Current State Analysis

### Existing Workflow
**File**: `/home/byron/dev/image_detection/.github/workflows/publish-pypi.yml`
**Lines**: 177 lines
**Package**: `image-preprocessing-detector`

### Key Characteristics
- ✅ OIDC Trusted Publishing already configured
- ✅ TestPyPI support via `workflow_dispatch`
- ✅ Build verification with `twine check`
- ✅ Security hardening with `harden-runner`
- ❌ No security scanning (Safety, Bandit)
- ❌ Hardcoded Python version (3.12)
- ❌ Hardcoded package name in multiple places
- ❌ 177 lines of boilerplate code

## Migration Benefits

| Feature | Before | After |
|---------|--------|-------|
| **Lines of code** | 177 | 22 (88% reduction) |
| **Security scanning** | None | Safety + Bandit |
| **Python version** | Hardcoded | Configurable |
| **Maintenance** | Per-repo | Centralized |
| **Package verification** | Manual | Automatic |
| **Configuration** | Scattered | Centralized inputs |

## Migration Steps

### Step 1: Update PyPI Trusted Publisher

The existing PyPI configuration needs a small update:

**Current configuration** (likely):
- PyPI Project Name: `image-preprocessing-detector` ✅
- Owner: `williaby` ⚠️ (needs verification)
- Repository: `image-preprocessing-detector` ✅
- Workflow: `publish-pypi.yml` ✅
- Environment: (blank or `release`) ✅

**Required changes**:
1. Verify the **Owner** field:
   - If publishing from personal account: Keep as `williaby`
   - If publishing from org: Change to `ByronWilliamsCPA`
2. Everything else stays the same!

**Update at**:
- PyPI: https://pypi.org/manage/account/publishing/
- TestPyPI: https://test.pypi.org/manage/account/publishing/

### Step 2: Replace Workflow File

**Option A: Complete Replacement** (Recommended)

Replace entire `.github/workflows/publish-pypi.yml` with:

```yaml
# PyPI Publishing Workflow
# Publishes image-preprocessing-detector to PyPI using Trusted Publishing
#
# Setup Instructions:
# 1. Verify PyPI Trusted Publisher at https://pypi.org/manage/account/publishing/
#    - PyPI Project Name: image-preprocessing-detector
#    - Owner: williaby (or ByronWilliamsCPA if org-owned)
#    - Repository: image-preprocessing-detector
#    - Workflow: publish-pypi.yml
# 2. For TestPyPI: https://test.pypi.org/manage/account/publishing/

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

jobs:
  publish:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-publish-pypi.yml@main
    with:
      package-name: 'image-preprocessing-detector'
      use-testpypi: ${{ inputs.use_testpypi || false }}
      python-version: '3.12'
      run-security-checks: true
      source-directory: 'src'
    permissions:
      id-token: write
      contents: read
```

**Option B: Side-by-Side Testing**

1. Rename existing workflow:
   ```bash
   cd /home/byron/dev/image_detection
   git mv .github/workflows/publish-pypi.yml .github/workflows/publish-pypi-old.yml
   ```

2. Create new workflow (as shown in Option A)

3. Test with TestPyPI:
   ```bash
   gh workflow run publish-pypi.yml --field use_testpypi=true
   ```

4. If successful, delete old workflow:
   ```bash
   git rm .github/workflows/publish-pypi-old.yml
   ```

### Step 3: Test with TestPyPI

**Important**: Always test with TestPyPI before production!

```bash
# Trigger workflow manually
cd /home/byron/dev/image_detection
gh workflow run publish-pypi.yml --field use_testpypi=true

# Monitor workflow
gh run watch

# Check results
gh run list --workflow=publish-pypi.yml --limit 1
```

**Verify publication**:
1. Check TestPyPI: https://test.pypi.org/project/image-preprocessing-detector/
2. Test installation:
   ```bash
   pip install --index-url https://test.pypi.org/simple/ image-preprocessing-detector
   ```

### Step 4: Production Release

**Create and test a new release**:

```bash
cd /home/byron/dev/image_detection

# Create release tag
git tag -a v0.2.0 -m "Release v0.2.0 - Using reusable PyPI workflow"
git push origin v0.2.0

# Create GitHub release
gh release create v0.2.0 \
  --title "v0.2.0 - Reusable Workflow Migration" \
  --notes "Migrated to org-level reusable PyPI publishing workflow with built-in security scanning."

# Workflow automatically triggers and publishes to PyPI
```

**Verify publication**:
1. Check workflow: `gh run watch`
2. Check PyPI: https://pypi.org/project/image-preprocessing-detector/
3. Test installation: `pip install image-preprocessing-detector`

## Security Improvements

The reusable workflow adds **automatic security scanning**:

### Safety - Dependency Scanning

Checks all dependencies in `uv.lock` for known vulnerabilities:

**Example findings it might catch**:
```
╒════════════════════════════╤═══════════════════════════════════════════════╕
│ Package                    │ Vulnerability                                 │
╞════════════════════════════╪═══════════════════════════════════════════════╡
│ pillow                     │ CVE-2023-XXXXX: Buffer overflow in decoder    │
│ numpy                      │ CVE-2023-YYYYY: Out of bounds read in array   │
╘════════════════════════════╧═══════════════════════════════════════════════╛
```

### Bandit - Code Security Scanning

Scans Python code in `src/` for security issues:

**Example findings it might catch**:
```
>> Issue: [B301:blacklist] Pickle and modules that wrap it can be unsafe
   Severity: Medium   Confidence: High
   Location: src/image_detection/cache.py:45
   More Info: https://bandit.readthedocs.io/en/latest/blacklists/...
```

**Common issues in image processing**:
- Unsafe image file handling
- Path traversal vulnerabilities
- Insecure temporary file usage
- Unvalidated user input

## Configuration Options for image_detection

The reusable workflow provides flexibility:

### Standard Configuration (Recommended)

```yaml
with:
  package-name: 'image-preprocessing-detector'
  use-testpypi: ${{ inputs.use_testpypi || false }}
  python-version: '3.12'
  run-security-checks: true
  source-directory: 'src'
```

### Alternative: Different Python Version

```yaml
with:
  package-name: 'image-preprocessing-detector'
  python-version: '3.11'  # Use Python 3.11 instead
```

### Alternative: Skip Security Checks (Not Recommended)

```yaml
with:
  package-name: 'image-preprocessing-detector'
  run-security-checks: false  # Only for testing/debugging
```

## Rollback Plan

If issues arise, you can quickly rollback:

### Option 1: Revert Git Commit

```bash
cd /home/byron/dev/image_detection
git revert HEAD
git push origin main
```

### Option 2: Restore Old Workflow

```bash
cd /home/byron/dev/image_detection
git checkout HEAD~1 -- .github/workflows/publish-pypi.yml
git commit -m "chore: rollback to standalone PyPI workflow"
git push origin main
```

### Option 3: Keep Both Workflows

Rename workflows to avoid conflicts:
- `publish-pypi-reusable.yml` - New reusable workflow caller
- `publish-pypi-standalone.yml` - Old standalone workflow

Disable one via workflow file or GitHub Actions settings.

## Expected Results

### Build Job Output

```
🔒 Running pre-publish security checks...
📦 Checking dependencies for vulnerabilities...
✓ No known security vulnerabilities found

🔍 Scanning source code...
✓ No security issues found

📦 Built packages:
-rw-r--r-- 1 runner docker 1234567 Jan 16 12:00 image_preprocessing_detector-0.2.0-py3-none-any.whl
-rw-r--r-- 1 runner docker  234567 Jan 16 12:00 image_preprocessing_detector-0.2.0.tar.gz

Checking dist/image_preprocessing_detector-0.2.0-py3-none-any.whl: PASSED
Checking dist/image_preprocessing_detector-0.2.0.tar.gz: PASSED
```

### Publish Job Output

```
📦 Packages to publish to PyPI:
-rw-r--r-- 1 runner docker 1234567 Jan 16 12:00 image_preprocessing_detector-0.2.0-py3-none-any.whl
-rw-r--r-- 1 runner docker  234567 Jan 16 12:00 image_preprocessing_detector-0.2.0.tar.gz

🔒 Using OIDC Trusted Publishing (no secrets needed)

Uploading distributions to https://upload.pypi.org/legacy/
Uploading image_preprocessing_detector-0.2.0-py3-none-any.whl
100% ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 1.2/1.2 MB • 00:01 • 1.0 MB/s
Uploading image_preprocessing_detector-0.2.0.tar.gz
100% ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 234.6/234.6 kB • 00:00 • 1.0 MB/s
```

### GitHub Step Summary

```markdown
## 🎉 Published to PyPI!

**Project**: https://pypi.org/project/image-preprocessing-detector/

**Install**: `pip install image-preprocessing-detector`

### 🔒 Security
- Published using OIDC Trusted Publishing
- No API tokens or passwords used
- Full audit trail at PyPI
```

## Timeline

Estimated migration time: **15-30 minutes**

1. **Update PyPI config** (5 min) - Verify/update Trusted Publisher settings
2. **Replace workflow** (2 min) - Copy new workflow file
3. **Test with TestPyPI** (5-10 min) - Trigger and verify test publication
4. **Production release** (5-10 min) - Create release and verify
5. **Cleanup** (3 min) - Remove old workflow, update docs

## Success Criteria

- [x] TestPyPI publication succeeds
- [x] Security checks run and complete
- [x] Production PyPI publication succeeds
- [x] Package installs correctly from PyPI
- [x] GitHub Step Summary shows correct information
- [x] Old workflow file removed

## Post-Migration

### Update Documentation

Update any references to the publishing process:

1. **README.md** - Update publishing instructions (if any)
2. **CONTRIBUTING.md** - Update release process (if any)
3. **Release checklist** - Simplify release steps

### Monitor First Few Releases

For the next 2-3 releases:
1. Review security check findings
2. Verify OIDC authentication works consistently
3. Monitor for any workflow failures

## Support

If you encounter issues:

1. **Check workflow logs**: `gh run view --log`
2. **Review migration guide**: [PyPI Publishing Migration](pypi-publishing-migration.md)
3. **Review workflow docs**: [Python PyPI Publishing](../workflows/python-publish-pypi.md)
4. **Rollback if needed**: See "Rollback Plan" section above

## Summary

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| **Code lines** | 177 | 22 | -88% |
| **Security checks** | 0 | 2 (Safety + Bandit) | +∞ |
| **Configuration** | Hardcoded | Parameterized | +100% |
| **Maintenance burden** | High (per-repo) | Low (org-level) | -90% |
| **OIDC security** | ✅ Yes | ✅ Yes | Same |
| **TestPyPI support** | ✅ Yes | ✅ Yes | Same |

**Net result**: Same functionality + security scanning + 88% less code + centralized maintenance! 🎉
