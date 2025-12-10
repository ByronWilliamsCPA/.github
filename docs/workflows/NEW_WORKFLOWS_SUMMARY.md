# New Reusable Workflows - Summary

This document summarizes the four new reusable workflows added to the organization's workflow library.

## Overview

| Workflow | Purpose | Key Features |
|----------|---------|--------------|
| **[Python Fuzzing](python-fuzzing.md)** | Security vulnerability detection | ClusterFuzzLite, multiple sanitizers, SARIF upload |
| **[Performance Regression](python-performance-regression.md)** | Performance monitoring | Baseline comparison, configurable thresholds, PR comments |
| **[SonarCloud](python-sonarcloud.md)** | Code quality analysis | Quality gates, coverage tracking, security scanning |
| **[Qlty Coverage](python-qlty-coverage.md)** | Coverage tracking | Centralized coverage, trend analysis, multi-format support |

## Workflow Comparison

### Python Fuzzing vs Security Analysis

| Feature | Fuzzing | Security Analysis |
|---------|---------|-------------------|
| **Approach** | Dynamic testing | Static analysis |
| **Detection** | Runtime crashes, memory issues | Known vulnerability patterns |
| **Coverage** | Edge cases, unexpected inputs | OWASP Top 10, CVEs |
| **When to Use** | Input parsing, file handling | Dependency scanning, code patterns |
| **Cost** | Higher (CPU intensive) | Lower (quick scans) |

**Recommendation:** Use **both** for comprehensive security coverage.

```yaml
jobs:
  security-static:
    uses: williaby/.github/.github/workflows/python-security-analysis.yml@main

  security-fuzzing:
    uses: williaby/.github/.github/workflows/python-fuzzing.yml@main
    with:
      fuzz-seconds: 600
```

### SonarCloud vs Qlty Coverage

| Feature | SonarCloud | Qlty Coverage |
|---------|------------|---------------|
| **Focus** | Code quality + coverage | Coverage only |
| **Metrics** | Bugs, smells, security, coverage | Coverage trends |
| **Analysis** | Full static analysis | Coverage upload |
| **Setup** | More complex | Simple token |
| **Cost** | Free for public repos | Free tier available |
| **Integration** | PR decoration, quality gates | Coverage diff |

**Recommendation:** Use **SonarCloud** for comprehensive quality tracking, or **Qlty** for lightweight coverage-only needs.

```yaml
# Option 1: Comprehensive (SonarCloud)
jobs:
  sonarcloud:
    uses: williaby/.github/.github/workflows/python-sonarcloud.yml@main
    secrets:
      SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}

# Option 2: Lightweight (Qlty)
jobs:
  ci:
    uses: williaby/.github/.github/workflows/python-ci.yml@main

  qlty:
    needs: ci
    uses: williaby/.github/.github/workflows/python-qlty-coverage.yml@main
    secrets:
      QLTY_COVERAGE_TOKEN: ${{ secrets.QLTY_COVERAGE_TOKEN }}
```

## Integration Patterns

### Complete Security Suite

```yaml
name: Security

on: [push, pull_request]

jobs:
  # Static analysis
  security-scan:
    uses: williaby/.github/.github/workflows/python-security-analysis.yml@main

  # Dynamic fuzzing (weekly)
  fuzzing:
    if: github.event_name == 'schedule'
    uses: williaby/.github/.github/workflows/python-fuzzing.yml@main
    with:
      fuzz-seconds: 1200

  # Code quality
  sonarcloud:
    uses: williaby/.github/.github/workflows/python-sonarcloud.yml@main
    secrets:
      SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
```

### Performance-Critical PRs

```yaml
name: Performance Gate

on:
  pull_request:
    paths:
      - 'src/core/**'
      - 'src/api/**'

jobs:
  performance:
    uses: williaby/.github/.github/workflows/python-performance-regression.yml@main
    with:
      benchmark-script: 'scripts/benchmark.py'
      regression-threshold: 5.0  # Strict 5% threshold
      fail-on-regression: true
```

### Quality-First Development

```yaml
name: Quality Gates

on: [push, pull_request]

jobs:
  ci:
    uses: williaby/.github/.github/workflows/python-ci.yml@main

  sonarcloud:
    needs: ci
    uses: williaby/.github/.github/workflows/python-sonarcloud.yml@main
    secrets:
      SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
    with:
      fail-on-quality-gate: true  # Block merge on failure

  performance:
    needs: ci
    uses: williaby/.github/.github/workflows/python-performance-regression.yml@main
    with:
      benchmark-script: 'scripts/benchmark.py'
      fail-on-regression: true
```

## Cost Optimization

### Fuzzing Optimization

**Before:** Per-PR fuzzing
```yaml
on: [pull_request]  # ~95 runs/month = $13/month
```

**After:** Weekly schedule
```yaml
on:
  schedule:
    - cron: '0 3 * * 1'  # ~5 runs/month = $1/month
  workflow_dispatch:     # Manual for critical PRs
```

**Savings:** 92% reduction (~$12/month)

### Performance Testing Optimization

**Targeted Path Triggers:**
```yaml
on:
  pull_request:
    paths:
      - 'src/performance-critical/**'
      - 'src/api/**'
```

Only run when performance-critical code changes.

### Quality Analysis Optimization

**Branch-Specific:**
```yaml
on:
  push:
    branches: [main, develop]  # Only on important branches
  pull_request:                # Always on PRs for decoration
```

## Setup Checklist

### 1. Python Fuzzing

- [ ] Create `fuzz/` directory with fuzzing harnesses
- [ ] Add `atheris` dependency to `pyproject.toml`
- [ ] Configure weekly schedule in workflow
- [ ] Enable SARIF upload for Security tab

### 2. Performance Regression

- [ ] Create benchmark script outputting JSON
- [ ] Add baseline file (optional) or generate from main
- [ ] Configure regression thresholds
- [ ] Set up PR path triggers

### 3. SonarCloud

- [ ] Sign up at [sonarcloud.io](https://sonarcloud.io)
- [ ] Import repository and note project key
- [ ] Generate token and add to secrets
- [ ] Configure quality gate thresholds
- [ ] Test PR decoration

### 4. Qlty Coverage

- [ ] Sign up at [qlty.sh](https://qlty.sh)
- [ ] Connect GitHub organization
- [ ] Generate coverage token
- [ ] Add QLTY_COVERAGE_TOKEN to secrets
- [ ] Configure coverage artifact name

## Migration Examples

All workflows include migration guides:

- **[Fuzzing Migration](../../examples/fuzzing-migration-example.md)** - From project-specific CIFuzzy
- **Performance Migration** - From inline benchmark steps
- **SonarCloud Migration** - From project-specific workflows
- **Qlty Migration** - From Codecov or Coveralls

## Documentation

Each workflow has comprehensive documentation:

| Workflow | Documentation | Examples |
|----------|---------------|----------|
| Fuzzing | [python-fuzzing.md](python-fuzzing.md) | 4 examples + migration guide |
| Performance | [python-performance-regression.md](python-performance-regression.md) | Coming soon |
| SonarCloud | [python-sonarcloud.md](python-sonarcloud.md) | Coming soon |
| Qlty Coverage | [python-qlty-coverage.md](python-qlty-coverage.md) | Coming soon |

## Benefits Summary

### Centralization

- **Before:** 70+ lines per workflow per project
- **After:** 10-20 lines calling reusable workflow
- **Maintenance:** Update once, propagate to all projects

### Consistency

- **Security Hardening:** harden-runner on all steps
- **Action Pinning:** Commit SHA pinning
- **Best Practices:** Consistent patterns organization-wide

### Features

- **Enhanced Error Handling:** Better failure messages
- **Configurable Inputs:** Flexible for different projects
- **Graceful Degradation:** Skip if tokens missing
- **Comprehensive Reporting:** GitHub step summaries

## Support

For issues or questions:

1. Check workflow-specific documentation
2. Review examples directory
3. Consult migration guides
4. Open issue at [williaby/.github](https://github.com/williaby/.github/issues)

---

**Next Steps:**

1. Choose workflows relevant to your project
2. Follow setup checklists
3. Test with manual workflow_dispatch
4. Monitor first few runs
5. Adjust thresholds as needed
