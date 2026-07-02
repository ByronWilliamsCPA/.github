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
| `system-deps-ubuntu` | string | no | `''` | APT packages to install on Ubuntu (space-separated, e.g., `libmagic-dev libffi-dev`) |
| `system-deps-macos` | string | no | `''` | Homebrew packages to install on macOS (space-separated, e.g., `libmagic`) |
| `system-deps-windows` | string | no | `''` | Chocolatey packages to install on Windows (space-separated) |
| `no-build` | boolean | no | `true` | Pass `--no-build` to `uv sync`/`uv run` commands (disable for projects with a build backend like hatchling) |

## Usage

```yaml
jobs:
  compatibility:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-compatibility.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    with:
      python-versions: '["3.11","3.12","3.13"]'
```
