# python-ci.yml -- Reusable Python CI workflow

The `python-ci.yml` reusable workflow runs the full Python quality stack
(format, lint, type check, test, security scan, dependency audit, LLM
governance) against a caller repository.

## Required directory layout

This workflow **requires** the caller repository to follow a Python `src/`
layout. By default it expects:

- A `src/` directory (overridable via the `source-directory` input)
- A `tests/` directory (overridable via the `test-directory` input)
- A `pyproject.toml` at the repository root declaring a Python package
  (PEP 621 `[project]` table or Poetry-style `[tool.poetry]`)

If either directory is missing, the workflow now fails fast at the
"Validate source layout" step with a clear actionable error, instead of
producing the older opaque `Failed to format src: No such file or directory`
failure.

## When to use this workflow

Use `python-ci.yml` for any repository that is a **Python package** with the
canonical src layout. Most ByronWilliamsCPA Python packages call this
workflow from their `.github/workflows/ci.yml`.

## When NOT to use it

Do not call `python-ci.yml` from:

- Configuration repositories (agent configs, Claude prompt repos, docs-only
  repositories)
- Repositories that are not Python at all

If you do, the validation step will fail. Write a hand-rolled CI workflow
instead that emits the `CI Gate` required status context using appropriate
tooling (yamllint, markdownlint, actionlint, em-dash check).

### Flat-layout Python packages

Flat-layout Python packages (no `src/` directory) are supported via input
overrides. Pass `source-directory: '.'` (or the actual package directory)
along with the matching `test-directory`, and the validation step will
locate the code without complaint:

```yaml
jobs:
  ci:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-ci.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    with:
      source-directory: '.'
      test-directory: tests
```

## Minimal usage

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  ci:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-ci.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    with:
      python-version: "3.12"
      coverage-threshold: 80
    secrets: inherit
```

## Inputs (selected)

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| `python-version` | string | `3.12` | Primary Python version for quality checks |
| `source-directory` | string | `src` | Directory containing the package source |
| `test-directory` | string | `tests` | Directory containing the test suite |
| `coverage-threshold` | number | `80` | Minimum coverage percentage |
| `enable-matrix-testing` | boolean | `false` | Enable tiered multi-version matrix testing |
| `parallel-tests` | boolean | `false` | Opt-in: run unit/integration/security as parallel jobs (`test-unit`, `test-integration`, `test-security`) instead of sequential steps in `quality-checks`, cutting wall-clock time on repos with a large integration suite. A `coverage-combine` job merges their coverage data back into the same `coverage-reports` artifact, so no caller-side change is needed to adopt it. **Requires** the caller's `pyproject.toml` to set `[tool.coverage.run] relative_files = true` — without it, `coverage combine` cannot correctly merge data recorded on three separate runners and the combined coverage percentage will be wrong. |

See the workflow file for the full input list.

## Rationale for the layout requirement

Every quality step in `python-ci.yml` (ruff format check, ruff lint,
basedpyright, vulture, pytest with coverage, bandit, LLM tag scan) reads
from `${{ inputs.source-directory }}`. If the directory does not exist, the
first step that runs against it errors out with a tool-specific message,
which is hard to diagnose from the caller side. The precondition step
exists so future misuse fails with the same actionable error every time.
