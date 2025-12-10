# Migrating from Project-Specific CIFuzzy to Reusable Workflow

This guide shows how to migrate from a project-specific ClusterFuzzLite workflow to the centralized reusable workflow.

## Before: Project-Specific Workflow

```yaml
# .github/workflows/cifuzzy.yml (OLD)
name: ClusterFuzzLite (Weekly)

on:
  schedule:
    - cron: '0 3 * * 1'
  workflow_dispatch:
  push:
    branches:
      - main

permissions: read-all

jobs:
  fuzzing:
    name: Build & Run Fuzzers
    runs-on: ubuntu-latest
    timeout-minutes: 30
    permissions:
      contents: read
      security-events: write

    steps:
      - name: Harden the runner
        uses: step-security/harden-runner@91182cccc01eb5e619899d80e4e971d6181294a7
        with:
          egress-policy: audit

      - name: Checkout repository
        uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683

      - name: Build Fuzzers
        id: build
        uses: google/clusterfuzzlite/actions/build_fuzzers@884713a6c30a92e5e8544c39945cd7cb630abcd1
        with:
          language: python
          dry-run: false

      - name: Run Fuzzers
        uses: google/clusterfuzzlite/actions/run_fuzzers@884713a6c30a92e5e8544c39945cd7cb630abcd1
        if: steps.build.outcome == 'success'
        with:
          fuzz-seconds: 1200
          language: python
          output-sarif: true
          sanitizer: address

      - name: Upload Crash Artifacts
        if: failure() && steps.build.outcome == 'success'
        uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02
        with:
          name: fuzzing-crashes-${{ github.run_id }}
          path: out/artifacts
          retention-days: 14

      - name: Upload SARIF Report
        if: always() && steps.build.outcome == 'success'
        uses: github/codeql-action/upload-sarif@48ab28a6f5dbc2a99bf1e0131198dd8f1df78169
        with:
          sarif_file: sarif/cifuzz.sarif
        continue-on-error: true
```

**Issues with Old Approach:**

- 70+ lines of duplicated workflow code
- Manual action SHA pinning and updates
- Inconsistent patterns across projects
- No reusability or centralized updates
- Missing features (corpus pruning, multi-sanitizer, etc.)

## After: Reusable Workflow

```yaml
# .github/workflows/fuzzing.yml (NEW)
name: Security Fuzzing

on:
  schedule:
    - cron: '0 3 * * 1'  # Weekly Monday 3 AM UTC
  workflow_dispatch:
  push:
    branches: [main]

permissions: read-all

jobs:
  fuzzing:
    uses: williaby/.github/.github/workflows/python-fuzzing.yml@main
    permissions:
      contents: read
      security-events: write
    with:
      fuzz-seconds: 1200
      sanitizer: 'address'
      upload-sarif: true
      crash-retention-days: 14
```

**Benefits:**

- ✅ **12 lines** instead of 70+ (83% reduction)
- ✅ **Centralized maintenance** - updates propagate automatically
- ✅ **Consistent security hardening** across all projects
- ✅ **Additional features** - corpus pruning, multi-sanitizer, better error handling
- ✅ **Better documentation** and examples
- ✅ **Auto-detection** of fuzzing directories

## Migration Steps

### 1. Ensure Fuzzing Directory Exists

The reusable workflow auto-detects:

- `fuzz/` (recommended)
- `tests/fuzz/`
- `fuzzing/`

```bash
# Check current structure
ls -la fuzz/ || ls -la tests/fuzz/ || ls -la fuzzing/

# If needed, move to standard location
mkdir -p fuzz
mv your-custom-fuzz-dir/* fuzz/
```

### 2. Verify Fuzzing Harnesses

Ensure files match naming pattern:

```bash
# Good
fuzz/fuzz_*.py
fuzz/*_fuzz.py

# Rename if needed
mv fuzz/test_parser.py fuzz/fuzz_parser.py
```

### 3. Update Workflow File

Replace project-specific workflow with reusable call:

```yaml
name: Security Fuzzing

on:
  schedule:
    - cron: '0 3 * * 1'
  workflow_dispatch:
  push:
    branches: [main]

permissions: read-all

jobs:
  fuzzing:
    uses: williaby/.github/.github/workflows/python-fuzzing.yml@main
    permissions:
      contents: read
      security-events: write
    with:
      fuzz-seconds: 1200
      sanitizer: 'address'
      upload-sarif: true
```

### 4. Test Locally (Optional)

Use dry-run to validate setup:

```yaml
jobs:
  fuzzing-test:
    uses: williaby/.github/.github/workflows/python-fuzzing.yml@main
    with:
      dry-run: true  # Build only, no execution
```

### 5. Commit and Push

```bash
git add .github/workflows/fuzzing.yml
git commit -m "refactor: migrate to reusable fuzzing workflow"
git push
```

### 6. Verify First Run

Manually trigger workflow:

1. Go to Actions tab
2. Select "Security Fuzzing" workflow
3. Click "Run workflow"
4. Monitor execution and check for crashes

## Configuration Mapping

| Old Configuration | New Input Parameter | Notes |
|-------------------|---------------------|-------|
| `fuzz-seconds: 1200` | `fuzz-seconds: 1200` | Same |
| `sanitizer: address` | `sanitizer: 'address'` | String format |
| `output-sarif: true` | `upload-sarif: true` | Renamed |
| `retention-days: 14` | `crash-retention-days: 14` | More specific |
| `timeout-minutes: 30` | `timeout-minutes: 30` | Same |
| N/A | `fail-on-crash: true` | New - controls failure |
| N/A | `enable-corpus-prune: false` | New - corpus optimization |

## Advanced Migration Scenarios

### Custom Fuzzing Directory

**Old:**

```yaml
# Custom directory handling in steps
steps:
  - name: Setup custom directory
    run: |
      export FUZZ_DIR=tests/security/fuzz
      # ... custom logic ...
```

**New:**

```yaml
with:
  fuzz-target-directory: 'tests/security/fuzz'
```

### Multiple Sanitizers

**Old:** Multiple workflow files or matrix strategy

```yaml
# .github/workflows/cifuzzy-address.yml
# .github/workflows/cifuzzy-undefined.yml
# ... separate files for each sanitizer ...
```

**New:** Single workflow with parallel jobs

```yaml
jobs:
  address-sanitizer:
    uses: williaby/.github/.github/workflows/python-fuzzing.yml@main
    with:
      sanitizer: 'address'

  undefined-sanitizer:
    uses: williaby/.github/.github/workflows/python-fuzzing.yml@main
    with:
      sanitizer: 'undefined'
```

See [examples/fuzzing-multi-sanitizer.yml](../examples/fuzzing-multi-sanitizer.yml)

## Validation Checklist

After migration, verify:

- [ ] Workflow file updated to reusable workflow call
- [ ] Fuzzing directory exists in standard location (or custom path specified)
- [ ] Fuzzing harnesses match naming pattern (`fuzz_*.py` or `*_fuzz.py`)
- [ ] Atheris dependency in `pyproject.toml`
- [ ] First manual run completes successfully
- [ ] SARIF results appear in Security tab
- [ ] Crash artifacts upload (if crashes found)

## Rollback Plan

If issues arise, temporarily revert:

```bash
# Revert to old workflow
git revert HEAD

# Or restore from backup
git checkout HEAD~1 .github/workflows/fuzzing.yml
git commit -m "revert: restore project-specific fuzzing workflow"
```

## Benefits After Migration

- **Automatic Updates:** Action SHA updates propagate automatically
- **Enhanced Features:** Corpus pruning, better error messages, auto-detection
- **Consistency:** Same pattern across all projects
- **Better Docs:** Comprehensive documentation and examples
- **Cost Tracking:** Centralized cost optimization recommendations

## Support

For issues during migration:

1. Check [python-fuzzing.md](../docs/workflows/python-fuzzing.md) documentation
2. Review [examples/](../examples/) for similar use cases
3. Run with `dry-run: true` to validate setup
4. Open issue at [williaby/.github](https://github.com/williaby/.github/issues)
