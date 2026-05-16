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
- Repositories with a flat Python layout (no `src/` directory)
- Repositories that are not Python at all

If you do, the validation step will fail. Choose an alternative:

- For **flat-layout Python packages**, pass `source-directory: '.'` (or the
  actual package directory) so the validation finds the code.
- For **non-Python or pure config repositories**, write a hand-rolled CI
  workflow that emits the `CI Gate` required status context using
  appropriate tooling (yamllint, markdownlint, actionlint, em-dash check).

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
    uses: ByronWilliamsCPA/.github/.github/workflows/python-ci.yml@main
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

See the workflow file for the full input list.

## Rationale for the layout requirement

Every quality step in `python-ci.yml` (ruff format check, ruff lint,
basedpyright, vulture, pytest with coverage, bandit, LLM tag scan) reads
from `${{ inputs.source-directory }}`. If the directory does not exist, the
first step that runs against it errors out with a tool-specific message,
which is hard to diagnose from the caller side. The precondition step
exists so future misuse fails with the same actionable error every time.

For the original investigation that prompted this hardening, see
`docs/superpowers/plans/2026-05-16-reusable-ci-workflow-audit.md` in the
downstream `.claude` configuration repo.
