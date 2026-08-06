# Python SonarCloud Analysis Workflow

Reusable GitHub Actions workflow for continuous code quality and security analysis using SonarCloud.

## Overview

SonarCloud provides static analysis for:

- **Code Quality**: Bugs, code smells, technical debt
- **Security**: Vulnerabilities, security hotspots (OWASP Top 10)
- **Test Coverage**: Track and trend coverage over time
- **Code Duplication**: Identify duplicated code blocks
- **Maintainability**: Technical debt and complexity metrics

## Quick Start

### 1. SonarCloud Setup

1. Visit [sonarcloud.io](https://sonarcloud.io) and sign in with GitHub
2. Import your repository
3. Note your organization and project key (format: `org_repo-name`)
4. Generate token at [sonarcloud.io/account/security](https://sonarcloud.io/account/security)
5. Add `SONAR_TOKEN` to repository secrets

### 2. Configure Workflow

```yaml
# .github/workflows/sonarcloud.yml
name: SonarCloud

on:
  push:
    branches: [main, develop]
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  sonarcloud:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-sonarcloud.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    secrets:
      SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
    with:
      sonar-organization: 'your-org'
      sonar-project-key: 'your-org_your-repo'
```

## Configuration Options

### Required Inputs

| Input | Type | Description |
|-------|------|-------------|
| `sonar-organization` | string | SonarCloud organization name |
| `sonar-project-key` | string | Project key (format: org_repo-name) |

### Optional Inputs

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| `python-version` | string | '3.12' | Single Python version used to build the project and run the analysis; feeds `actions/setup-python` |
| `sonar-python-version` | string | '' | Python versions the source supports, comma-separated (`3.11,3.12,3.13`). Sets `sonar.python.version`. Falls back to `python-version` when empty. See [Declaring supported source versions](#declaring-supported-source-versions) |
| `source-directory` | string | 'src' | Source code directory |
| `coverage-paths` | string | 'coverage.xml' | Coverage report paths (comma-separated) |
| `coverage-exclusions` | string | See below | Paths to exclude from coverage |
| `test-exclusions` | string | '' | Paths to exclude from analysis |
| `extra-dependencies` | string | 'dev' | Additional uv sync extras |
| `pytest-args` | string | '' | Additional pytest arguments |
| `fail-on-quality-gate` | boolean | false | Fail workflow if quality gate fails |
| `skip-if-no-token` | boolean | true | Skip gracefully if SONAR_TOKEN missing |
| `timeout-minutes` | number | 15 | Job timeout |
| `additional-sonar-args` | string | '' | Extra SonarQube scanner arguments |
| `coverage-artifact-retention` | number | 7 | Days to retain artifacts |

**Default Coverage Exclusions:**

```text
**/tests/**,**/validation/**,**/benchmarks/**,**/scripts/**
```

### Required Secrets

| Secret | Description |
|--------|-------------|
| `SONAR_TOKEN` | SonarCloud authentication token (optional if `skip-if-no-token: true`) |

### Declaring supported source versions

`python-version` and `sonar-python-version` answer two different questions. Keep them
separate:

| Input | Question it answers | Cardinality |
|-------|---------------------|-------------|
| `python-version` | Which interpreter builds the project and runs the scan? | Exactly one (`actions/setup-python` rejects a list) |
| `sonar-python-version` | Which versions must the source code remain valid on? | One or more, comma-separated |

Set `sonar-python-version` whenever your `requires-python` range is wider than the single
version used to build:

```yaml
with:
  python-version: '3.12'                    # builds and scans on 3.12
  sonar-python-version: '3.11,3.12,3.13'    # source must stay valid on all three
```

**Why it matters.** SonarPython gates version-specific rules on *every* declared version,
not the highest one. Declaring only the build version tells the analyzer the project is
3.12-only, so it raises 3.12+ syntax rules (PEP 695 `type` aliases, `python:S6794` and
`python:S6796`) against code that still has to run on 3.11. Adding 3.11 to the list
correctly silences them.

**The inverse also holds, and it loses findings silently.** Because the gate requires all
declared versions to meet a rule's threshold, declaring versions *below* your real floor
suppresses rules you actually want. A project whose `requires-python` is `>=3.12` that
declares `3.9,3.12` gets no 3.10+, 3.11+, or 3.12+ rules at all, with no warning. Declare
the range that matches `requires-python` and nothing wider.

**Format.** Comma-separated `MAJOR.MINOR` values. Whitespace around the commas and at the
ends is tolerated and stripped, so both `3.11,3.12` and SonarSource's own documented
`3.11, 3.12` spacing work. Anything else fails the job with an explicit message rather than
reaching the scanner as a malformed argument: a patch version (`3.12.1`), a range operator
(`>=3.11`), a trailing comma, or whitespace inside a version (`3 .11`), which is rejected
rather than silently normalized into a different version.

## Usage Examples

### Basic Configuration

```yaml
name: Code Quality

on:
  push:
    branches: [main]
  pull_request:

jobs:
  sonarcloud:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-sonarcloud.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    secrets:
      SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
    with:
      sonar-organization: 'acme-corp'
      sonar-project-key: 'acme-corp_my-project'
```

### Custom Source Directory

```yaml
jobs:
  sonarcloud:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-sonarcloud.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    secrets:
      SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
    with:
      sonar-organization: 'acme-corp'
      sonar-project-key: 'acme-corp_my-project'
      source-directory: 'app'  # Custom source path
      coverage-paths: 'coverage.xml,coverage-integration.xml'
```

### Multiple Coverage Reports

```yaml
jobs:
  sonarcloud:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-sonarcloud.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    secrets:
      SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
    with:
      sonar-organization: 'acme-corp'
      sonar-project-key: 'acme-corp_my-project'
      coverage-paths: 'coverage.xml,integration-coverage.xml,e2e-coverage.xml'
```

### Strict Quality Gate Enforcement

```yaml
jobs:
  sonarcloud:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-sonarcloud.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    secrets:
      SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
    with:
      sonar-organization: 'acme-corp'
      sonar-project-key: 'acme-corp_my-project'
      fail-on-quality-gate: true  # Block merge on failure
```

### Custom Exclusions

```yaml
jobs:
  sonarcloud:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-sonarcloud.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    secrets:
      SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
    with:
      sonar-organization: 'acme-corp'
      sonar-project-key: 'acme-corp_my-project'
      coverage-exclusions: '**/tests/**,**/migrations/**,**/fixtures/**'
      test-exclusions: '**/integration_tests/**'
```

### Additional Scanner Arguments

```yaml
jobs:
  sonarcloud:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-sonarcloud.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    secrets:
      SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
    with:
      sonar-organization: 'acme-corp'
      sonar-project-key: 'acme-corp_my-project'
      additional-sonar-args: >
        -Dsonar.projectVersion=${{ github.ref_name }}
        -Dsonar.links.homepage=https://example.com
        -Dsonar.links.ci=${{ github.server_url }}/${{ github.repository }}/actions
```

## SonarCloud Properties File

For advanced configuration, create `sonar-project.properties` in repository root:

```properties
# Project identification
sonar.organization=acme-corp
sonar.projectKey=acme-corp_my-project
sonar.projectName=My Project
sonar.projectVersion=1.0.0

# Source configuration
sonar.sources=src
sonar.tests=tests
# Every version the source must stay valid on, not just the build version.
sonar.python.version=3.11,3.12,3.13

# Coverage configuration
sonar.python.coverage.reportPaths=coverage.xml
sonar.coverage.exclusions=**/tests/**,**/migrations/**

# Code analysis
sonar.exclusions=**/generated/**
sonar.test.exclusions=**/integration_tests/**

# Additional settings
sonar.sourceEncoding=UTF-8
```

**Note:** Workflow inputs override properties file settings. The workflow always passes
`-Dsonar.python.version` on the command line, so a `sonar.python.version` key in this file
is ignored; set the `sonar-python-version` input instead.

## Quality Gate Configuration

Configure quality gates in SonarCloud dashboard:

### Recommended Thresholds

| Metric | Threshold | Type |
|--------|-----------|------|
| Coverage on New Code | ≥ 80% | New Code |
| Duplicated Lines on New Code | ≤ 3% | New Code |
| Maintainability Rating on New Code | ≤ A | New Code |
| Reliability Rating on New Code | ≤ A | New Code |
| Security Rating on New Code | ≤ A | New Code |
| Security Hotspots Reviewed | 100% | Overall |

### Custom Quality Gate

1. Go to SonarCloud dashboard
2. **Organization Settings** → **Quality Gates**
3. Create new gate or modify existing
4. Set conditions for Overall Code and New Code
5. Assign to project

## PR Integration

SonarCloud automatically decorates pull requests with:

- **Overall Status**: Quality gate pass/fail
- **New Issues**: Bugs, vulnerabilities, code smells
- **Coverage Impact**: Coverage change on PR
- **Inline Comments**: Issues annotated in code

### Example PR Comment

```text
SonarCloud Quality Gate: Passed ✅

3 new issues:
- 1 Bug
- 2 Code Smells

Coverage: 85.2% (+2.1%)

View details: https://sonarcloud.io/dashboard?id=acme-corp_my-project&pullRequest=42
```

## Troubleshooting

### SONAR_TOKEN Not Configured

**Error:** Workflow skipped

**Solution:**

1. Generate token at [sonarcloud.io/account/security](https://sonarcloud.io/account/security)
2. Add to repository: **Settings** → **Secrets** → **Actions**
3. Name: `SONAR_TOKEN`

**Alternative:** Set `skip-if-no-token: false` to require token

### Coverage Report Not Found

**Warning:** "Coverage report not found"

**Causes:**

- Tests failed to run
- Coverage not generated in XML format
- Incorrect `coverage-paths` configuration

**Solution:**

```yaml
# Ensure pytest generates coverage.xml
pytest --cov=src --cov-report=xml:coverage.xml
```

### Quality Gate Failed

**Error:** "Quality Gate failed"

**Review:**

1. Visit SonarCloud dashboard
2. Check **New Code** tab for issues
3. Address bugs, vulnerabilities, code smells
4. Improve coverage if below threshold

### Shallow Clone Warning

**Warning:** "Shallow clone detected"

**Solution:** Workflow automatically uses `fetch-depth: 0`

### Analysis Timeout

**Error:** Job timeout after 15 minutes

**Solution:**

```yaml
with:
  timeout-minutes: 30  # Increase for large projects
```

## Integration Patterns

### Combined with CI

```yaml
name: CI and Quality

on: [push, pull_request]

jobs:
  ci:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-ci.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1

  sonarcloud:
    needs: ci
    uses: ByronWilliamsCPA/.github/.github/workflows/python-sonarcloud.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    secrets:
      SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
    with:
      sonar-organization: 'acme-corp'
      sonar-project-key: 'acme-corp_my-project'
```

### With Security Analysis

```yaml
jobs:
  security:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-security-analysis.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1

  sonarcloud:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-sonarcloud.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    secrets:
      SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
    with:
      sonar-organization: 'acme-corp'
      sonar-project-key: 'acme-corp_my-project'
```

## Metrics Explained

### Code Quality Metrics

| Metric | Description |
|--------|-------------|
| **Bugs** | Issues that represent coding errors |
| **Code Smells** | Maintainability issues |
| **Technical Debt** | Estimated time to fix all code smells |
| **Duplications** | Percentage of duplicated code |
| **Cognitive Complexity** | How difficult code is to understand |

### Security Metrics

| Metric | Description |
|--------|-------------|
| **Vulnerabilities** | Security issues (OWASP Top 10) |
| **Security Hotspots** | Code requiring security review |
| **Security Rating** | A (best) to E (worst) |

### Coverage Metrics

| Metric | Description |
|--------|-------------|
| **Line Coverage** | % of lines executed by tests |
| **Branch Coverage** | % of branches executed by tests |
| **Coverage on New Code** | Coverage of code added in PR |

## Best Practices

### 1. Configure Quality Gate

Set realistic thresholds for your project maturity level.

### 2. Focus on New Code

Prioritize quality on new code additions over fixing legacy issues.

### 3. Review Security Hotspots

Manually review all security hotspots flagged by SonarCloud.

### 4. Address Technical Debt

Track technical debt trend and allocate time for remediation.

### 5. Maintain High Coverage

Target ≥80% coverage on new code to prevent regressions.

### 6. Use Exclusions Wisely

Exclude generated code, migrations, and test fixtures from analysis.

## Resources

- [SonarCloud Documentation](https://docs.sonarsource.com/sonarcloud/)
- [Python Analysis](https://docs.sonarsource.com/sonarcloud/enriching/languages/python/)
- [Quality Gates](https://docs.sonarsource.com/sonarcloud/improving/quality-gates/)
- [PR Decoration](https://docs.sonarsource.com/sonarcloud/improving/pull-request-analysis/)
- [Coverage Import](https://docs.sonarsource.com/sonarcloud/enriching/test-coverage/python/)

## Related Workflows

- **[Python Security Analysis](python-security-analysis.md)** - CodeQL, Bandit, Safety
- **[Python CI](python-ci.md)** - Testing and linting
- **[Qlty Coverage](python-qlty-coverage.md)** - Alternative coverage tracking

---

**See Also:**

- [USAGE_EXAMPLES.md](../../USAGE_EXAMPLES.md) - Complete workflow examples
- [examples/](../../examples/) - Ready-to-use configurations
