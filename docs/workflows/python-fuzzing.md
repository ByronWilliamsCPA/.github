# Python Fuzzing Workflow (ClusterFuzzLite)

Reusable GitHub Actions workflow for continuous fuzzing of Python projects using Google's ClusterFuzzLite.

## Overview

ClusterFuzzLite provides automated fuzzing to detect:

- Memory safety vulnerabilities (buffer overflows, use-after-free)
- Undefined behavior
- Input validation issues
- Edge cases in parsing/processing logic
- Security vulnerabilities in file/data handling

Perfect for projects that process untrusted input (images, PDFs, JSON, XML, user data, etc.).

## Quick Start

### 1. Create Fuzzing Harnesses

Create a `fuzz/` directory with fuzzing targets:

```python
# fuzz/fuzz_image_loader.py
import atheris
import sys
from your_package import load_image


def TestOneInput(data):
    """Fuzz target for image loading."""
    try:
        load_image(data)
    except (ValueError, TypeError, IOError):
        # Expected exceptions - not bugs
        pass


if __name__ == "__main__":
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()
```

### 2. Add Atheris Dependency

```toml
# pyproject.toml
[tool.poetry.dependencies]
atheris = {version = "^2.3.0", optional = true}

[tool.poetry.extras]
fuzzing = ["atheris"]
```

### 3. Configure Workflow

```yaml
# .github/workflows/fuzzing.yml
name: Fuzzing

on:
  schedule:
    - cron: '0 3 * * 1'  # Weekly Monday 3 AM UTC
  workflow_dispatch:  # Manual trigger
  push:
    branches: [main]

jobs:
  fuzzing:
    uses: williaby/.github/.github/workflows/python-fuzzing.yml@main
    with:
      fuzz-seconds: 1200  # 20 minutes
      sanitizer: 'address'
      upload-sarif: true
```

## Configuration Options

### Inputs

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| `fuzz-seconds` | number | 600 | Duration to run fuzzers (in seconds) |
| `sanitizer` | string | 'address' | Sanitizer to use (address, undefined, memory) |
| `upload-sarif` | boolean | true | Upload SARIF results to GitHub Security |
| `crash-retention-days` | number | 14 | Days to retain crash artifacts |
| `python-version` | string | '3.12' | Python version for fuzzing |
| `dry-run` | boolean | false | Build fuzzers only, no execution |
| `fuzz-target-directory` | string | '' | Custom fuzzing directory (auto-detect if empty) |
| `timeout-minutes` | number | 30 | Job timeout in minutes |
| `fail-on-crash` | boolean | true | Fail workflow if crashes are found |
| `enable-corpus-prune` | boolean | false | Enable corpus pruning to minimize test cases |

### Sanitizer Options

#### Address Sanitizer (Default)

Detects:

- Buffer overflows
- Use-after-free
- Double-free
- Memory leaks

```yaml
with:
  sanitizer: 'address'
```

#### Undefined Behavior Sanitizer

Detects:

- Integer overflow
- Division by zero
- Null pointer dereference
- Misaligned memory access

```yaml
with:
  sanitizer: 'undefined'
```

#### Memory Sanitizer (Linux only)

Detects:

- Uninitialized memory reads

```yaml
with:
  sanitizer: 'memory'
```

## Usage Examples

### Weekly Security Fuzzing

```yaml
name: Weekly Fuzzing

on:
  schedule:
    - cron: '0 3 * * 1'  # Monday 3 AM UTC
  workflow_dispatch:

jobs:
  fuzzing:
    uses: williaby/.github/.github/workflows/python-fuzzing.yml@main
    with:
      fuzz-seconds: 1200  # Extended 20-minute run
      sanitizer: 'address'
      upload-sarif: true
      crash-retention-days: 30
```

**Cost Optimization:** Weekly runs vs. per-PR can save ~92% in CI costs.

### Security-Critical PR Testing

```yaml
name: PR Fuzzing (Manual)

on:
  workflow_dispatch:

jobs:
  fuzzing:
    uses: williaby/.github/.github/workflows/python-fuzzing.yml@main
    with:
      fuzz-seconds: 600  # Shorter 10-minute run
      sanitizer: 'address'
      fail-on-crash: true
```

### Multi-Sanitizer Analysis

```yaml
name: Comprehensive Fuzzing

on:
  schedule:
    - cron: '0 3 * * 0'  # Sunday 3 AM UTC

jobs:
  address-sanitizer:
    uses: williaby/.github/.github/workflows/python-fuzzing.yml@main
    with:
      fuzz-seconds: 900
      sanitizer: 'address'

  undefined-sanitizer:
    uses: williaby/.github/.github/workflows/python-fuzzing.yml@main
    with:
      fuzz-seconds: 900
      sanitizer: 'undefined'
```

### Custom Fuzzing Directory

```yaml
jobs:
  fuzzing:
    uses: williaby/.github/.github/workflows/python-fuzzing.yml@main
    with:
      fuzz-target-directory: 'tests/security/fuzz'
      fuzz-seconds: 1200
```

### Dry Run (Build Validation)

```yaml
jobs:
  fuzzing-build-test:
    uses: williaby/.github/.github/workflows/python-fuzzing.yml@main
    with:
      dry-run: true  # Only build, don't execute
```

## Fuzzing Harness Best Practices

### Structure

```python
import atheris
import sys
from your_package import process_data


@atheris.instrument_func  # Optional: instrument for better coverage
def TestOneInput(data):
    """Fuzz target for data processing.

    Args:
        data: Raw fuzzing input (bytes)
    """
    # Skip empty input
    if len(data) < 4:
        return

    try:
        # Your code under test
        result = process_data(data)

        # Optional: Add assertions
        assert result is not None
        assert isinstance(result, dict)

    except (ValueError, TypeError) as e:
        # Expected exceptions - not bugs
        # Don't catch Exception or BaseException
        pass


if __name__ == "__main__":
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()
```

### Common Patterns

#### Image Processing

```python
def TestOneInput(data):
    from PIL import Image
    import io

    try:
        img = Image.open(io.BytesIO(data))
        img.verify()
    except (OSError, ValueError):
        pass
```

#### PDF Processing

```python
def TestOneInput(data):
    from pypdf import PdfReader
    import io

    try:
        reader = PdfReader(io.BytesIO(data))
        for page in reader.pages:
            _ = page.extract_text()
    except Exception:
        # PDF parsing can throw various exceptions
        pass
```

#### JSON/XML Parsing

```python
def TestOneInput(data):
    import json

    try:
        obj = json.loads(data)
        # Process parsed object
        validate_schema(obj)
    except (json.JSONDecodeError, ValueError):
        pass
```

## Directory Structure

ClusterFuzzLite auto-detects fuzzing targets in:

1. `fuzz/` (recommended)
2. `tests/fuzz/`
3. `fuzzing/`

Or specify custom path via `fuzz-target-directory` input.

### Example Layout

```
project/
├── fuzz/
│   ├── fuzz_image_loader.py
│   ├── fuzz_pdf_loader.py
│   └── fuzz_json_parser.py
├── src/
│   └── your_package/
└── pyproject.toml
```

## Security Integration

### SARIF Upload

Results automatically upload to GitHub Security tab:

```yaml
with:
  upload-sarif: true  # Default
```

View findings at: `https://github.com/<owner>/<repo>/security/code-scanning`

### Crash Artifacts

When crashes are detected:

1. Artifacts uploaded with crash details
2. Retention configurable via `crash-retention-days`
3. Download from Actions artifacts tab

### Fail on Crash

Control workflow failure behavior:

```yaml
with:
  fail-on-crash: true  # Fail workflow (default)
```

```yaml
with:
  fail-on-crash: false  # Continue workflow, upload artifacts
```

## Cost Optimization

### Schedule Optimization

**Per-PR Fuzzing (Expensive):**

```yaml
on: [pull_request, push]  # ~95 runs/month
```

**Weekly Fuzzing (Recommended):**

```yaml
on:
  schedule:
    - cron: '0 3 * * 1'  # ~5 runs/month
  workflow_dispatch:      # Manual for critical PRs
```

**Savings:** ~92% reduction in CI costs (~$12/month for typical project)

### Duration Tuning

| Duration | Use Case |
|----------|----------|
| 300s (5 min) | Quick PR validation |
| 600s (10 min) | Standard weekly fuzzing |
| 1200s (20 min) | Deep security analysis |
| 3600s (1 hour) | Comprehensive testing |

Longer runs find more edge cases but increase costs linearly.

## Troubleshooting

### Build Failures

**Error:** "No fuzzing directory found"

**Solution:** Create `fuzz/` directory with fuzzing harnesses, or specify custom path:

```yaml
with:
  fuzz-target-directory: 'your/custom/path'
```

**Error:** "Atheris not installed"

**Solution:** Add to dependencies:

```toml
[tool.poetry.dependencies]
atheris = "^2.3.0"
```

### No Fuzzers Detected

**Cause:** No files matching `fuzz_*.py` or `*_fuzz.py`

**Solution:** Rename fuzzing harnesses to match pattern:

```bash
# Good
fuzz/fuzz_parser.py
fuzz/image_fuzz.py

# Bad
fuzz/test_parser.py
fuzz/parser_test.py
```

### Crashes Not Detected

**Cause:** Fuzzing duration too short

**Solution:** Increase `fuzz-seconds`:

```yaml
with:
  fuzz-seconds: 1200  # 20 minutes
```

**Cause:** Exception handling too broad

**Solution:** Only catch expected exceptions:

```python
# ❌ Bad - hides all crashes
try:
    process(data)
except Exception:
    pass

# ✅ Good - allows crash detection
try:
    process(data)
except (ValueError, TypeError):
    pass
```

## Advanced Configuration

### Corpus Pruning

Minimize test case corpus for faster fuzzing:

```yaml
with:
  enable-corpus-prune: true
```

### Custom Timeout

Adjust job timeout for longer fuzzing runs:

```yaml
with:
  timeout-minutes: 60  # For 3600s fuzzing
```

### Multiple Python Versions

Test across Python versions:

```yaml
jobs:
  fuzzing-py311:
    uses: williaby/.github/.github/workflows/python-fuzzing.yml@main
    with:
      python-version: '3.11'

  fuzzing-py312:
    uses: williaby/.github/.github/workflows/python-fuzzing.yml@main
    with:
      python-version: '3.12'
```

## Performance Metrics

Typical fuzzing performance (20-minute run):

- **Executions:** 100K-10M+ per fuzzer
- **Coverage:** 60-90% code coverage
- **Memory:** 1-2 GB peak usage
- **CPU:** 100% utilization (single-threaded)

## Resources

- [ClusterFuzzLite Documentation](https://google.github.io/clusterfuzzlite/)
- [Atheris Python Fuzzer](https://github.com/google/atheris)
- [OSS-Fuzz Integration](https://github.com/google/oss-fuzz)
- [Fuzzing Best Practices](https://google.github.io/fuzzing/docs/good-fuzz-target/)

## Related Workflows

- **[Python Security Analysis](python-security-analysis.md)** - Static security scanning
- **[Python CI](python-ci.md)** - Comprehensive testing
- **[Python Release](python-release.md)** - Secure releases with SBOM

---

**See Also:**

- [USAGE_EXAMPLES.md](../../USAGE_EXAMPLES.md) - Complete workflow examples
- [examples/](../../examples/) - Ready-to-use configurations
