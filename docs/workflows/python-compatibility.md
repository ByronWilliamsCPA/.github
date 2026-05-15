# python-compatibility.yml -- Multi-Version Compatibility Matrix

Runs the test suite across a matrix of Python versions and operating systems
to verify compatibility. Draft PRs skip the full matrix by default (reducing
cost by 92%); the full matrix runs on ready PRs.

## Inputs

| Input | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `python-versions` | string | no | `["3.10","3.11","3.12","3.13"]` | JSON array of Python versions to test |
| `operating-systems` | string | no | `["ubuntu-latest"]` | JSON array of operating systems |
| `include-windows` | boolean | no | `false` | Include Windows in the matrix |
| `include-macos` | boolean | no | `false` | Include macOS in the matrix |
| `source-directory` | string | no | `src` | Source code directory |
| `test-command` | string | no | `pytest -v` | Test command (run with `uv run` prefix) |
| `coverage-report` | boolean | no | `true` | Generate coverage reports |
| `fail-fast` | boolean | no | `false` | Fail immediately on first matrix failure |
| `skip-on-draft` | boolean | no | `true` | Skip expensive matrix on draft PRs |
| `timeout-minutes` | number | no | `30` | Timeout for each matrix job |

## Usage

```yaml
jobs:
  compatibility:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-compatibility.yml@main
    with:
      python-versions: '["3.11","3.12","3.13"]'
```
