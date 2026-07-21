# Usage Examples for Reusable Workflows

## Quick Start

### Minimal Setup (Use All Defaults)

Create `.github/workflows/ci.yml` in your Python repo:

```yaml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:

jobs:
  ci:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-ci.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    secrets:
      CODECOV_TOKEN: ${{ secrets.CODECOV_TOKEN }}
```

This will:
- Test on Python 3.10, 3.11, 3.12, 3.13 (default matrix)
- Run MyPy, Ruff, and pytest
- Require 80% code coverage
- Upload coverage to Codecov if token provided

---

## Customization Examples

### Example 1: Custom Python Versions

Test only on Python 3.11 and 3.12:

```yaml
name: CI

on: [push, pull_request]

jobs:
  ci:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-ci.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    with:
      python-versions: '["3.11", "3.12"]'
    secrets:
      CODECOV_TOKEN: ${{ secrets.CODECOV_TOKEN }}
```

### Example 2: Higher Coverage Threshold

Require 90% coverage:

```yaml
name: CI

on: [push, pull_request]

jobs:
  ci:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-ci.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    with:
      coverage-threshold: 90
    secrets:
      CODECOV_TOKEN: ${{ secrets.CODECOV_TOKEN }}
```

### Example 3: Custom Source/Test Directories

If your project structure is different:

```yaml
name: CI

on: [push, pull_request]

jobs:
  ci:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-ci.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    with:
      source-directory: 'app'
      test-directory: 'tests/unit'
    secrets:
      CODECOV_TOKEN: ${{ secrets.CODECOV_TOKEN }}
```

### Example 4: Disable Type Checking

Skip MyPy if your project doesn't use type hints:

```yaml
name: CI

on: [push, pull_request]

jobs:
  ci:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-ci.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    with:
      run-mypy: false
    secrets:
      CODECOV_TOKEN: ${{ secrets.CODECOV_TOKEN }}
```

### Example 5: Skip Linting (Not Recommended)

If you only want testing:

```yaml
name: CI

on: [push, pull_request]

jobs:
  ci:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-ci.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    with:
      run-ruff: false
      run-mypy: false
```

### Example 6: Full Customization

All options configured:

```yaml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  ci:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-ci.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    with:
      python-versions: '["3.10", "3.11", "3.12"]'
      source-directory: 'src/myapp'
      test-directory: 'tests'
      coverage-threshold: 85
      run-mypy: true
      run-ruff: true
      mypy-strict: true
    secrets:
      CODECOV_TOKEN: ${{ secrets.CODECOV_TOKEN }}
```

---

## Multiple Jobs Example

You can call multiple reusable workflows:

```yaml
name: Complete CI/CD

on: [push, pull_request]

jobs:
  # Testing and quality
  ci:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-ci.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    with:
      python-versions: '["3.11", "3.12"]'
      coverage-threshold: 85
    secrets:
      CODECOV_TOKEN: ${{ secrets.CODECOV_TOKEN }}

  # Security scanning
  security:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-security-analysis.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    if: github.event_name == 'pull_request'

  # Documentation
  docs:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-docs.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    if: github.ref == 'refs/heads/main'
```

---

## Publishing Example

### PyPI Publishing with OIDC

```yaml
name: Publish to PyPI

on:
  release:
    types: [published]

jobs:
  publish:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-publish-pypi.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    permissions:
      id-token: write  # Required for OIDC
      contents: read
```

**No secrets needed!** Just configure OIDC at PyPI:
1. Go to https://pypi.org/manage/account/publishing/
2. Add publisher:
   - Repository: `yourorg/yourrepo`
   - Workflow: `publish.yml`
3. Done! Workflow uses OIDC automatically

---

## Dependency Provenance Example

### Weekly Transitive-Provenance Report (Sticky Issue)

Deterministic, keyless report that shows which DIRECT dependency introduces each
insecure TRANSITIVE package. No secrets, no hosted-scanner quota, no Anthropic
API key. Posts a sticky GitHub issue and uploads the report as an artifact.

Create `.github/workflows/dependency-provenance.yml`:

```yaml
name: Dependency Provenance

on:
  schedule:
    - cron: '23 6 * * 1'   # weekly, Monday 06:23 UTC (off-peak, non-:00)
  workflow_dispatch:

jobs:
  provenance:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-dependency-provenance.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    permissions:
      contents: read
      issues: write   # only the post-issue job needs this
    with:
      python-version: '3.12'
      open-issue: true
```

This will:
- Detect the ecosystem (Python `uv.lock` / `requirements*.txt`, frontend `package.json`)
- Run OSV-Scanner (keyless) to find vulnerable packages
- Trace each back to its introducing direct dependency (`uv tree --invert` / `npm why`)
- Post/update a sticky issue and upload a `dependency-provenance-report` artifact

The gating OSV-Scanner job in `python-sbom.yml` still owns the merge gate; this
workflow is a reporter that explains where each vulnerable package comes from.
See [docs/workflows/python-dependency-provenance.md](docs/workflows/python-dependency-provenance.md).

---

## Version Pinning

Every push to `main` cuts an immutable semver point tag (`vX.Y.Z`) via
`release-tag.yml`. The org tag-protection ruleset blocks re-pointing any `v*`
tag, so **there is no floating major tag** (no moving `@v1`); a tag, once
published, always resolves to the same commit. Callers choose between two
supported pin forms:

- **`@<sha>` with a release-tag comment**: full 40-character commit SHA of a
  release. Recommended default: immune to tag rewrites, and Renovate advances
  the pin automatically as new releases land (this is also what compliance
  check CI-005 requires).
- **`@vX.Y.Z`**: immutable point tag for exact-version pinning when you update
  deliberately rather than via Renovate.

`@main` is **not** recommended for any caller. A push to `main` takes effect
in every consumer instantly, with no review and no rollback path. Use it only
for short-lived workflow development on a fork or a feature branch in this
repo.

### Use a SHA Pin (Recommended)

Pin to the full commit SHA of a release tag and record the version in a
trailing comment. Renovate reads the comment and opens a PR advancing both
the SHA and the comment on each new release:

```yaml
jobs:
  ci:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-ci.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
```

### Use a Point Tag (Pin Once, Update Deliberately)

Pin to an immutable point tag:

```yaml
jobs:
  ci:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-ci.yml@v7.0.1
```

**Choosing a strategy:**

| Caller profile | Recommended pin |
| --- | --- |
| Standard production project | `@<sha> # vX.Y.Z` (auto-managed by Renovate) |
| Compliance-sensitive / regulated | `@<sha> # vX.Y.Z` |
| Repos without Renovate | `@vX.Y.Z`, updated deliberately |
| Active workflow development on this repo | `@<feature-branch>` (temporary) |

---

## Real-World Examples

### Example: FastAPI Application

```yaml
name: FastAPI CI

on:
  push:
    branches: [main, develop]
  pull_request:

jobs:
  ci:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-ci.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    with:
      python-versions: '["3.11", "3.12"]'
      source-directory: 'app'
      test-directory: 'tests'
      coverage-threshold: 90
      run-mypy: true
      run-ruff: true
    secrets:
      CODECOV_TOKEN: ${{ secrets.CODECOV_TOKEN }}

  security:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-security-analysis.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    needs: ci
```

### Example: CLI Tool

```yaml
name: CLI Tool CI

on: [push, pull_request]

jobs:
  test:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-ci.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    with:
      # Test on multiple Python versions for CLI compatibility
      python-versions: '["3.9", "3.10", "3.11", "3.12", "3.13"]'
      source-directory: 'src/mytool'
      test-directory: 'tests'
      coverage-threshold: 75
```

### Example: Library Package

```yaml
name: Library CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-ci.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    with:
      python-versions: '["3.10", "3.11", "3.12"]'
      coverage-threshold: 95  # High coverage for library
      mypy-strict: true       # Strict type checking

  publish:
    needs: test
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    uses: ByronWilliamsCPA/.github/.github/workflows/python-publish-pypi.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    permissions:
      id-token: write
```

---

## Matrix Strategy Within Reusable Workflow

The reusable workflow handles matrix internally, so you don't need to:

### ❌ DON'T Do This (Redundant Matrix)

```yaml
jobs:
  test:
    strategy:
      matrix:
        python-version: [3.11, 3.12]  # ❌ Don't do matrix in calling workflow
    uses: ByronWilliamsCPA/.github/.github/workflows/python-ci.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    with:
      python-versions: '["3.11", "3.12"]'
```

### ✅ DO This (Let Reusable Workflow Handle Matrix)

```yaml
jobs:
  test:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-ci.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    with:
      python-versions: '["3.11", "3.12"]'  # ✅ Pass array, workflow handles matrix
```

---

## Conditional Execution

### Run on Specific Branches Only

```yaml
jobs:
  ci:
    if: github.ref == 'refs/heads/main' || github.event_name == 'pull_request'
    uses: ByronWilliamsCPA/.github/.github/workflows/python-ci.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
```

### Skip CI on Documentation Changes

```yaml
on:
  push:
    paths-ignore:
      - 'docs/**'
      - '*.md'

jobs:
  ci:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-ci.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
```

---

## Debugging

### View Workflow Runs

Workflow runs appear in **your repo's Actions tab**, not the `.github` repo.

### Common Issues

**Issue**: "Workflow not found"
**Fix**: Check the `uses:` path is exactly `ByronWilliamsCPA/.github/.github/workflows/python-ci.yml@d5cf99101d4150ae5832d154cb42993705a09e31`; the trailing `# vX.Y.Z` release comment is not part of the path

**Issue**: "permissions denied"
**Fix**: Add `permissions:` block in calling workflow if needed

**Issue**: "input validation failed"
**Fix**: Ensure `python-versions` is valid JSON array: `'["3.11", "3.12"]'`

---

## Available Workflows

| Workflow | Purpose | Required Secrets |
|----------|---------|------------------|
| `python-ci.yml` | Testing, linting, type checking | `CODECOV_TOKEN` (optional) |
| `python-publish-pypi.yml` | Publish to PyPI | None (uses OIDC) |
| `python-security-analysis.yml` | Security scanning | None |
| `python-docs.yml` | Documentation build | None |
| `python-codecov.yml` | Coverage reporting | `CODECOV_TOKEN` |
| `python-release.yml` | Release automation | None |
| `python-sonarcloud.yml` | SonarCloud analysis | `SONAR_TOKEN` |
| `python-dependency-provenance.yml` | Weekly transitive-provenance report (sticky issue) | None |

---

## Full Input Reference

### python-ci.yml

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| `python-versions` | string (JSON array) | `["3.10", "3.11", "3.12", "3.13"]` | Python versions to test |
| `source-directory` | string | `src` | Source code directory |
| `test-directory` | string | `tests` | Test directory |
| `coverage-threshold` | number | `80` | Min coverage % |
| `run-mypy` | boolean | `true` | Run type checking |
| `run-ruff` | boolean | `true` | Run linting |
| `mypy-strict` | boolean | `true` | Use strict MyPy |

**Secrets**:
- `CODECOV_TOKEN` (optional): Codecov upload token

---

## Migration from Local Workflows

### Before (Local .github/workflows/ci.yml)

```yaml
name: CI
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@df4cb1c069e1874edd31b4311f1884172cec0e10  # v6.0.3
      - uses: actions/setup-python@a309ff8b426b58ec0e2a45f0f869d46889d02405  # v6.2.0
        with:
          python-version: '3.12'
      - run: pip install -e '.[dev]'
      - run: pytest
      - run: mypy src
      - run: ruff check
```

### After (Using Reusable Workflow)

```yaml
name: CI
on: [push, pull_request]

jobs:
  ci:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-ci.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    secrets:
      CODECOV_TOKEN: ${{ secrets.CODECOV_TOKEN }}
```

**Benefits**:
- ✅ 50 lines → 7 lines
- ✅ Security fixes auto-propagate
- ✅ Consistent across all repos
- ✅ Matrix testing included
- ✅ Coverage tracking built-in

---

## Next Steps

1. Create `.github/workflows/ci.yml` in your Python repo
2. Copy one of the examples above
3. Customize inputs as needed
4. Push and watch it run!
5. Check your repo's Actions tab for results

---

## Questions?

For more information:

- [docs/integrations/qlty-cloud.md](docs/integrations/qlty-cloud.md) - Qlty Cloud integration guide
- [README.md](README.md) - Main repository documentation
- [GitHub Reusable Workflows Docs](https://docs.github.com/en/actions/using-workflows/reusing-workflows)
