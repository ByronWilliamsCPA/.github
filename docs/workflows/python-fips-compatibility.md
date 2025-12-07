# Python FIPS Compatibility Workflow

## Overview

This reusable workflow validates FIPS 140-2/140-3 compliance for Python projects that use cryptographic operations. FIPS (Federal Information Processing Standards) mode is required for:

- US Government systems
- Healthcare systems (HIPAA compliance)
- Financial services
- Ubuntu LTS systems with `fips-updates` package

## Features

- **Static Analysis**: Detects non-FIPS cryptographic algorithms in code
- **Dependency Scanning**: Identifies problematic packages
- **Fix Hints**: Provides actionable suggestions for remediation
- **PR Integration**: Automatic comments on pull requests
- **Runtime Testing**: Optional simulated FIPS environment testing
- **Flexible Configuration**: Customizable severity levels and paths

## Usage

### Basic Usage

Add to your repository's `.github/workflows/fips-compatibility.yml`:

```yaml
name: FIPS Compatibility

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

permissions:
  contents: read
  pull-requests: write

jobs:
  fips-check:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-fips-compatibility.yml@main
    permissions:
      contents: read
      pull-requests: write
```

### Advanced Configuration

```yaml
jobs:
  fips-check:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-fips-compatibility.yml@main
    with:
      # Treat warnings as errors (default: false)
      strict-mode: true

      # Include test files in analysis (default: true)
      include-tests: false

      # Show fix hints in output (default: true)
      fix-hints: true

      # Artifact retention period in days (default: 30)
      artifact-retention-days: 90

      # Python version to use (default: '3.12')
      python-version: '3.11'

      # Path to FIPS check script (default: scripts/check_fips_compatibility.py)
      script-path: 'tools/fips_checker.py'

      # Enable runtime FIPS test (default: false)
      enable-runtime-test: true
    permissions:
      contents: read
      pull-requests: write
```

### Scheduled Runs with Manual Override

```yaml
name: FIPS Compatibility

on:
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 10 * * 1'  # Weekly on Monday
  workflow_dispatch:
    inputs:
      strict_mode:
        description: 'Treat warnings as errors'
        type: boolean
        default: false

jobs:
  fips-check:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-fips-compatibility.yml@main
    with:
      strict-mode: ${{ github.event.inputs.strict_mode || false }}
      enable-runtime-test: ${{ github.event_name == 'schedule' }}
```

## Inputs

| Input | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `strict-mode` | boolean | No | `false` | Treat warnings as errors |
| `include-tests` | boolean | No | `true` | Include test files in FIPS analysis |
| `fix-hints` | boolean | No | `true` | Show fix hints in output |
| `artifact-retention-days` | number | No | `30` | Days to retain compliance artifacts |
| `python-version` | string | No | `'3.12'` | Python version to use for checks |
| `script-path` | string | No | `'scripts/check_fips_compatibility.py'` | Path to FIPS check script |
| `enable-runtime-test` | boolean | No | `false` | Enable runtime FIPS compatibility test |

## Permissions Required

The workflow requires the following permissions:

```yaml
permissions:
  contents: read          # Read repository contents
  pull-requests: write    # Comment on PRs
```

## Outputs & Artifacts

### Artifacts

The workflow uploads the following artifacts:

- **fips-compatibility-report**
  - `fips-report.txt`: Human-readable report
  - `fips-report.json`: Machine-readable JSON report
  - Retention: Configurable (default 30 days)

### PR Comments

For pull requests, the workflow posts a comment with:

- Summary table (Errors, Warnings, Info counts)
- Overall status (PASSED, NEEDS REVIEW, FAILED)
- Link to detailed workflow run
- FIPS overview and common fixes

### GitHub Step Summary

Available in the workflow run summary:

- Compliance status
- Issue breakdown table
- Links to FIPS resources

## Common FIPS Issues & Fixes

### Issue: MD5 Usage

**Problem:**
```python
import hashlib
hash = hashlib.md5(data)  # ❌ Fails in FIPS mode
```

**Fix:**
```python
import hashlib
# For non-security purposes (checksums, cache keys)
hash = hashlib.md5(data, usedforsecurity=False)  # ✅

# For security purposes, use FIPS-approved algorithm
hash = hashlib.sha256(data)  # ✅
```

### Issue: Weak Ciphers

**Problem:**
```python
from cryptography.hazmat.primitives.ciphers import algorithms
cipher = algorithms.DES(key)  # ❌ DES not FIPS-approved
```

**Fix:**
```python
from cryptography.hazmat.primitives.ciphers import algorithms
cipher = algorithms.AES(key)  # ✅ AES is FIPS-approved
```

### Issue: Non-FIPS Dependencies

**Problem:**
```
bcrypt==4.1.2  # ❌ Uses Blowfish (not FIPS-approved)
```

**Fix:**
```
argon2-cffi==23.1.0  # ✅ Argon2 can work in FIPS mode
# Or use passlib with bcrypt_sha256 for FIPS compliance
```

## FIPS Check Script Requirements

The workflow expects a Python script at the configured path (default: `scripts/check_fips_compatibility.py`) with the following interface:

### Command-Line Arguments

```bash
python scripts/check_fips_compatibility.py \
  [--strict] \
  [--fix-hints] \
  [--include-tests] \
  [--json]
```

### Output Format (JSON)

```json
{
  "summary": {
    "errors": 0,
    "warnings": 0,
    "info": 0
  },
  "issues": [
    {
      "file": "src/crypto.py",
      "line": 42,
      "severity": "error",
      "code": "FIPS-MD5",
      "message": "MD5 usage without usedforsecurity=False",
      "fix_hint": "Add usedforsecurity=False parameter"
    }
  ]
}
```

### Exit Codes

- `0`: No issues (or only info/warnings in non-strict mode)
- `1`: Errors found (or warnings in strict mode)

## Example Check Script

A minimal FIPS compatibility checker:

```python
#!/usr/bin/env python3
"""FIPS compatibility checker."""
import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

def check_file(file_path: Path) -> list[dict[str, Any]]:
    """Check a single file for FIPS issues."""
    issues = []
    content = file_path.read_text()

    # Check for MD5 without usedforsecurity
    md5_pattern = r'hashlib\.md5\([^)]+\)(?!\s*,\s*usedforsecurity\s*=\s*False)'
    for match in re.finditer(md5_pattern, content):
        line_num = content[:match.start()].count('\n') + 1
        issues.append({
            'file': str(file_path),
            'line': line_num,
            'severity': 'error',
            'code': 'FIPS-MD5',
            'message': 'MD5 usage without usedforsecurity=False',
            'fix_hint': 'Add usedforsecurity=False or use SHA-256'
        })

    return issues

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--strict', action='store_true')
    parser.add_argument('--fix-hints', action='store_true')
    parser.add_argument('--include-tests', action='store_true')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()

    all_issues = []
    src_path = Path('src')

    for py_file in src_path.rglob('*.py'):
        all_issues.extend(check_file(py_file))

    errors = sum(1 for i in all_issues if i['severity'] == 'error')
    warnings = sum(1 for i in all_issues if i['severity'] == 'warning')
    info = sum(1 for i in all_issues if i['severity'] == 'info')

    if args.json:
        print(json.dumps({
            'summary': {'errors': errors, 'warnings': warnings, 'info': info},
            'issues': all_issues
        }))
    else:
        for issue in all_issues:
            print(f"{issue['file']}:{issue['line']} [{issue['severity']}] {issue['message']}")
            if args.fix_hints and 'fix_hint' in issue:
                print(f"  Fix: {issue['fix_hint']}")

    return 1 if errors > 0 or (args.strict and warnings > 0) else 0

if __name__ == '__main__':
    sys.exit(main())
```

## Integration with CI/CD

### Required Workflow

```yaml
# Always check on PRs
on:
  pull_request:
    paths:
      - 'src/**/*.py'
      - 'pyproject.toml'
```

### Optional Scheduled Scan

```yaml
# Weekly full scan
on:
  schedule:
    - cron: '0 10 * * 1'
```

### Manual Trigger

```yaml
# Allow manual runs with options
on:
  workflow_dispatch:
    inputs:
      strict_mode:
        type: boolean
        default: false
```

## Troubleshooting

### Script Not Found

**Issue:** `FIPS check script not found at scripts/check_fips_compatibility.py`

**Solution:**
1. Create the script at the expected path, or
2. Configure `script-path` input to point to your script location

### False Positives

**Issue:** Non-security MD5 usage flagged as error

**Solution:** Add `usedforsecurity=False` parameter:
```python
hashlib.md5(data, usedforsecurity=False)
```

### Dependency Conflicts

**Issue:** Package requires non-FIPS algorithm

**Solution:**
1. Check for FIPS-compatible alternatives
2. Consider vendoring and patching if necessary
3. Document exceptions with business justification

## Resources

- [FIPS 140-2 Standard](https://csrc.nist.gov/pubs/fips/140-2/upd2/final)
- [FIPS 140-3 Standard](https://csrc.nist.gov/pubs/fips/140-3/final)
- [Python FIPS Mode (RHEL)](https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/8/html/security_hardening/using-the-system-wide-cryptographic-policies_security-hardening)
- [NIST Approved Algorithms](https://csrc.nist.gov/projects/cryptographic-algorithm-validation-program)

## Contributing

To improve this workflow:

1. Submit issues to [ByronWilliamsCPA/.github](https://github.com/ByronWilliamsCPA/.github/issues)
2. Propose enhancements via pull requests
3. Share your FIPS check script improvements

## License

This workflow is part of the ByronWilliamsCPA organization's shared GitHub Actions and follows the repository's license.
