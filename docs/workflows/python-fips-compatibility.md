# Python FIPS Compatibility Workflow

## Overview

This reusable workflow validates FIPS 140-2/140-3 compliance and post-quantum
cryptography (PQC) readiness for Python projects that use cryptographic
operations. FIPS (Federal Information Processing Standards) mode is required for:

- US Government systems
- Healthcare systems (HIPAA compliance)
- Financial services
- Ubuntu LTS systems with `fips-updates` package

PQC readiness checking supports the org's transition to hybrid cryptography:
NIST finalized FIPS 203 (ML-KEM), FIPS 204 (ML-DSA) and FIPS 205 (SLH-DSA) in
August 2024, and NIST IR 8547 schedules deprecation of 112-bit-strength
classical algorithms after 2030 (disallowed after 2035). Because ML-KEM and
ML-DSA are NIST-approved, FIPS compliance and hybrid PQC are the same goal:
the migration target is hybrid key establishment (a classical exchange
combined with ML-KEM per NIST SP 800-56C Rev. 2).

## Features

- **Static Analysis**: Detects non-FIPS cryptographic algorithms in code
- **PQC Readiness Analysis**: Flags quantum-vulnerable key establishment and
  signatures (`PQC-*` rule codes) with a three-stage ratchet (`pqc-mode`)
- **Org-Central Checker**: Rules roll out fleet-wide from
  `ByronWilliamsCPA/.github`; no per-repo script needed
- **Algorithm Inventory**: CBOM-style `fips-inventory.json` artifact for
  fleet-wide migration tracking
- **Dependency Scanning**: Identifies problematic packages
- **Fix Hints**: Provides suggestions for remediation
- **PR Integration**: Automatic comments on pull requests
- **Runtime Testing**: Optional simulated FIPS test plus a hybrid-PQC
  capability probe of the runner and dependency stack
- **Flexible Configuration**: Customizable severity levels and paths

## Checker Resolution

The workflow resolves which checker script to run in this order:

1. **Caller-local override**: a script at `script-path`
   (default `scripts/check_fips_compatibility.py`) in the calling repository,
   if present. Custom checkers must honor the CLI and JSON contract below.
2. **Org-central checker** (default path): `scripts/check_fips_compatibility.py`
   fetched from `ByronWilliamsCPA/.github` at `central-checker-ref`. This is
   how FIPS and PQC rule updates reach every consuming repo from one place.
3. **None available**: the check soft-skips with a warning, or fails when
   `fail-on-missing-script: true`. Docs-only repos (no `pyproject.toml`)
   always skip gracefully.

Set `use-central-checker: false` to disable the fallback (restores the pre-v8
behavior of requiring a repo-local script).

`central-checker-ref` defaults to `main` so rule updates apply immediately.
Repos wanting supply-chain rigor should pin an immutable point tag or a full
40-character SHA (the org tag ruleset makes `v*` tags immutable).

## PQC Readiness and the Hybrid Migration

### The pqc-mode ratchet

| Mode | Behavior |
|------|----------|
| `off` | PQC rules skipped; algorithm inventory still collected |
| `warn` (default) | PQC findings reported in the report, PR comment and summary; never fail the build; exempt from `strict-mode` escalation so the classic FIPS ratchet and the PQC ratchet move independently |
| `error` | Warning-level PQC findings (quantum-vulnerable key establishment, non-validated PQC dependencies) are escalated to errors and gate the build |

The intended migration sequence per repo: `off` or `warn` for visibility,
inventory review, remediation planning, then `error` as the milestone gate.

### PQC rule codes (org-central checker)

| Code | Default severity | Meaning |
|------|------------------|---------|
| `PQC-CLASSICAL-KEX` | warning | Classical-only key establishment (ECDH, X25519/X448, RSA-OAEP key transport); quantum-vulnerable with harvest-now-decrypt-later risk |
| `PQC-CLASSICAL-SIG` | info | Classical-only signatures (ECDSA, RSA-PSS, Ed25519/Ed448, DSA) |
| `PQC-TLS-CONTEXT` | info | TLS context creation; hybrid groups (e.g. X25519MLKEM768) require OpenSSL 3.5+ at runtime |
| `PQC-DEP-CAPABILITY` | info | `cryptography` version constraint may exclude ML-KEM/ML-DSA-capable releases |
| `PQC-DEP-NONVALIDATED` | warning | PQC library (liboqs, pqcrypto) that is not FIPS 140-3 validated; the FIPS-approved component of a hybrid scheme must stay inside a validated module boundary |
| `PQC-NO-CAPABILITY` | info | Quantum-vulnerable crypto present but no PQC-capable dependency or code path exists yet |

Suppress a finding on a specific line with a trailing comment:
`# fips: ignore` or `# fips: ignore[PQC-CLASSICAL-KEX]`.

### Algorithm inventory (CBOM)

Every crypto touchpoint (hashes, ciphers, key establishment, signatures, TLS
contexts, PQC primitives) is recorded in the JSON report's `inventory` key and
uploaded as `fips-inventory.json`. Aggregating these artifacts across repos
gives the fleet-wide cryptographic inventory that NIST/CISA migration guidance
treats as step one; the `quantum_vulnerable` counter is the migration progress
metric.

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
    # Renovate advances this pin; pqc-mode and the other v8 inputs require
    # the first release cut from v8.0.0 or later.
    uses: ByronWilliamsCPA/.github/.github/workflows/python-fips-compatibility.yml@aaf22b70696819de5122dcde708406aaff968484 # v7.0.20
    permissions:
      contents: read
      pull-requests: write
```

No repo-local checker script is needed: the org-central checker is used by
default.

### Advanced Configuration

```yaml
jobs:
  fips-check:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-fips-compatibility.yml@aaf22b70696819de5122dcde708406aaff968484 # v7.0.20
    with:
      # Treat classic FIPS warnings as errors (default: false).
      # PQC findings are governed by pqc-mode, not strict-mode.
      strict-mode: true

      # PQC readiness ratchet: off | warn | error (default: warn)
      pqc-mode: error

      # Fall back to the org-central checker (default: true)
      use-central-checker: true

      # Ref of ByronWilliamsCPA/.github for the central checker (default: main).
      # Pin an immutable point tag or full SHA for supply-chain rigor.
      central-checker-ref: 'main'

      # Fail instead of soft-skipping when no checker is available (default: false)
      fail-on-missing-script: false

      # Include test files in analysis (default: true)
      include-tests: false

      # Show fix hints in output (default: true)
      fix-hints: true

      # Artifact retention period in days (default: 30)
      artifact-retention-days: 90

      # Python version to use (default: '3.12')
      python-version: '3.11'

      # Caller-local override checker (default: scripts/check_fips_compatibility.py)
      script-path: 'tools/fips_checker.py'

      # Enable runtime FIPS test (default: false). With pqc-mode not 'off',
      # a second matrix leg probes hybrid-PQC capability of the environment.
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
    uses: ByronWilliamsCPA/.github/.github/workflows/python-fips-compatibility.yml@aaf22b70696819de5122dcde708406aaff968484 # v7.0.20
    with:
      strict-mode: ${{ github.event.inputs.strict_mode || false }}
      enable-runtime-test: ${{ github.event_name == 'schedule' }}
```

## Inputs

| Input | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `strict-mode` | boolean | No | `false` | Treat classic FIPS warnings as errors (PQC findings are governed by `pqc-mode`) |
| `pqc-mode` | string | No | `'warn'` | PQC readiness ratchet: `off`, `warn`, or `error` |
| `use-central-checker` | boolean | No | `true` | Fall back to the org-central checker when no local script exists |
| `central-checker-ref` | string | No | `'main'` | Ref of `ByronWilliamsCPA/.github` to fetch the central checker from |
| `fail-on-missing-script` | boolean | No | `false` | Fail instead of soft-skipping when no checker is available |
| `include-tests` | boolean | No | `true` | Include test files in FIPS analysis |
| `fix-hints` | boolean | No | `true` | Show fix hints in output |
| `artifact-retention-days` | number | No | `30` | Days to retain compliance artifacts |
| `python-version` | string | No | `'3.12'` | Python version to use for checks |
| `script-path` | string | No | `'scripts/check_fips_compatibility.py'` | Path to a caller-local override checker |
| `enable-runtime-test` | boolean | No | `false` | Enable runtime FIPS compatibility test |
| `no-build` | boolean | No | `true` | Pass `--no-build` to uv sync/run commands |

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
  - `fips-inventory.json`: CBOM-style algorithm inventory (org-central checker,
    or any custom checker emitting the v8 contract)
  - Retention: Configurable (default 30 days)

### PR Comments

For pull requests, the workflow posts a comment with:

- Summary table (Errors, Warnings, Info, PQC readiness findings)
- Overall status (PASSED, NEEDS REVIEW, FAILED) and the active PQC mode
- Link to detailed workflow run
- FIPS/PQC overview and common fixes

### GitHub Step Summary

Available in the workflow run summary:

- Compliance status and checker source (`local` or `central`)
- Issue breakdown table including PQC findings
- Links to FIPS 140-2/140-3, FIPS 203/204/205 and NIST IR 8547

## Runtime Test Matrix

With `enable-runtime-test: true` the runtime job runs as a matrix:

- **classical**: the simulated FIPS-mode import test (unchanged from v7).
  Full FIPS validation still requires a FIPS-enabled kernel.
- **pqc-probe** (only when `pqc-mode` is not `off`): reports whether the
  runner's OpenSSL exposes ML-KEM/ML-DSA and whether the project's
  `cryptography` build has ML-KEM bindings. The probe is informational by
  design; it reflects the environment, not the caller's code, so it never
  fails the build. It becomes a hard gate only once fleet baseline images
  ship OpenSSL 3.5+.

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
cipher = algorithms.TripleDES(key)  # ❌ Not FIPS-approved
```

**Fix:**

```python
from cryptography.hazmat.primitives.ciphers import algorithms
cipher = algorithms.AES(key)  # ✅ AES is FIPS-approved
```

### Issue: Non-FIPS Dependencies

**Problem:**

```text
bcrypt==4.1.2  # ❌ Uses Blowfish (not FIPS-approved)
```

**Fix:**

```text
passlib[pbkdf2]==1.7.4  # ✅ PBKDF2-HMAC-SHA256 (NIST SP 800-132 approved)
# Note: argon2-cffi is NOT FIPS-approved; use PBKDF2 or another NIST-approved KDF
```

### Issue: Classical-Only Key Establishment (PQC)

**Problem:**

```python
shared = private_key.exchange(ec.ECDH(), peer_public_key)  # 🧭 PQC-CLASSICAL-KEX
```

**Fix:** plan a hybrid scheme; combine the classical shared secret with an
ML-KEM (FIPS 203) shared secret per NIST SP 800-56C Rev. 2. For TLS, hybrid
negotiation (X25519MLKEM768) is handled by the runtime once it links
OpenSSL 3.5+; track readiness with the `pqc-probe` runtime leg. Until the
stack supports it, keep the finding visible in `warn` mode rather than
suppressing it.

## Custom Checker Contract

The org-central checker is the default. A repository may override it with its
own script at `script-path`, which must implement this interface.

### Command-Line Arguments

```bash
python scripts/check_fips_compatibility.py \
  [--strict] \
  [--fix-hints] \
  [--include-tests] \
  [--json] \
  [--pqc-mode {off,warn,error}]
```

**BREAKING (v8.0.0):** the workflow always passes `--pqc-mode`. Custom
checkers written against the v7 contract must add the flag (one argparse
line); a checker that does not recognize it exits non-zero and the check
fails. A minimal custom checker can accept and ignore it:

```python
parser.add_argument("--pqc-mode", choices=("off", "warn", "error"), default="warn")
```

### Output Format (JSON)

```json
{
  "summary": {
    "errors": 0,
    "warnings": 1,
    "info": 0,
    "pqc_findings": 1
  },
  "pqc_mode": "warn",
  "issues": [
    {
      "file": "src/crypto.py",
      "line": 42,
      "severity": "warning",
      "code": "PQC-CLASSICAL-KEX",
      "message": "Classical-only key establishment is quantum-vulnerable",
      "fix_hint": "Plan hybrid key establishment (ML-KEM + classical)",
      "pqc": true
    }
  ],
  "inventory": {
    "algorithms": [
      {
        "algorithm": "ECDH",
        "category": "key-establishment",
        "file": "src/crypto.py",
        "line": 42,
        "quantum_vulnerable": true
      }
    ],
    "stats": {
      "total": 1,
      "quantum_vulnerable": 1,
      "by_category": { "key-establishment": 1 }
    }
  }
}
```

`summary.errors`, `summary.warnings` and `summary.info` are required.
`summary.pqc_findings` and `inventory` are part of the v8 contract; the
workflow defaults them to `0`/absent for older custom checkers, so v7-era
JSON (plus the `--pqc-mode` flag) keeps working.

### Exit Codes

- `0`: No issues (or only info/warnings in non-strict mode; PQC findings in
  `off`/`warn` mode never affect the exit code)
- `1`: Errors found, classic warnings in strict mode, or escalated PQC
  findings in `error` mode

### Reference Implementation

See
[`scripts/check_fips_compatibility.py`](../../scripts/check_fips_compatibility.py)
in `ByronWilliamsCPA/.github` for the canonical implementation of the
contract, including the PQC ruleset and the inventory generator.

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

### Check Skipped

**Issue:** `No FIPS checker available; the FIPS compatibility check will be skipped.`

**Solution:**
1. Leave `use-central-checker: true` (default) so the org-central checker is used, or
2. Ship a custom checker and point `script-path` at it.
3. Set `fail-on-missing-script: true` to turn this soft-skip into a failure
   once the repo is expected to be covered.

### Custom Checker Rejects --pqc-mode

**Issue:** `error: unrecognized arguments: --pqc-mode`

**Solution:** the v8 workflow always passes `--pqc-mode`. Add the flag to the
custom checker's argparse (see Custom Checker Contract), or delete the custom
script to adopt the org-central checker.

### False Positives

**Issue:** Non-security MD5 usage flagged as error

**Solution:** Add `usedforsecurity=False` parameter:

```python
hashlib.md5(data, usedforsecurity=False)
```

For other rules, suppress a specific line with `# fips: ignore[CODE]`.

### Dependency Conflicts

**Issue:** Package requires non-FIPS algorithm

**Solution:**
1. Check for FIPS-compatible alternatives
2. Consider vendoring and patching if necessary
3. Document exceptions with business justification

## Resources

- [FIPS 140-2 Standard](https://csrc.nist.gov/pubs/fips/140-2/upd2/final)
- [FIPS 140-3 Standard](https://csrc.nist.gov/pubs/fips/140-3/final)
- [FIPS 203: ML-KEM](https://csrc.nist.gov/pubs/fips/203/final)
- [FIPS 204: ML-DSA](https://csrc.nist.gov/pubs/fips/204/final)
- [FIPS 205: SLH-DSA](https://csrc.nist.gov/pubs/fips/205/final)
- [NIST IR 8547: Transition to Post-Quantum Cryptography Standards](https://csrc.nist.gov/pubs/ir/8547/ipd)
- [NIST SP 800-56C Rev. 2 (hybrid shared secrets)](https://csrc.nist.gov/pubs/sp/800/56/c/r2/final)
- [Python FIPS Mode (RHEL)](https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/8/html/security_hardening/using-the-system-wide-cryptographic-policies_security-hardening)
- [NIST Approved Algorithms](https://csrc.nist.gov/projects/cryptographic-algorithm-validation-program)

## Contributing

To improve this workflow:

1. Submit issues to [ByronWilliamsCPA/.github](https://github.com/ByronWilliamsCPA/.github/issues)
2. Propose enhancements via pull requests; PQC/FIPS rule changes belong in
   `scripts/check_fips_compatibility.py` so they roll out fleet-wide
3. Share your FIPS check script improvements

## License

This workflow is part of the ByronWilliamsCPA organization's shared GitHub Actions and follows the repository's license.
