# python-qlty-gate.yml -- Reusable Qlty check gate

Runs `qlty check` as a blocking CI gate and, optionally, as an informational
full-codebase health scan. Use it as a required PR gate (diff mode) and as a
scheduled debt tracker (full scan mode).

## Operating modes

| Mode | Trigger | Behavior |
|------|---------|----------|
| Diff (default) | `check-all: false` | Analyzes only files changed against `upstream`. Requires `upstream` to be set; the gate fails fast when neither `check-all` nor `upstream` is provided. |
| Full scan | `check-all: true` | Runs `qlty check --all` over the whole codebase. Pair with `no-fail: true` for non-blocking scheduled health scans. |

## Minimal usage (PR gate)

```yaml
jobs:
  qlty-gate:
    if: github.event_name == 'pull_request'
    uses: ByronWilliamsCPA/.github/.github/workflows/python-qlty-gate.yml@v1
    with:
      fail-level: medium
      upstream: origin/${{ github.base_ref }}
    permissions:
      contents: read
```

## Minimal usage (weekly health scan)

```yaml
jobs:
  qlty-gate:
    if: github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'
    uses: ByronWilliamsCPA/.github/.github/workflows/python-qlty-gate.yml@v1
    with:
      fail-level: high
      check-all: true
      no-fail: true
    permissions:
      contents: read
```

## Inputs

| Input | Default | Purpose |
|-------|---------|---------|
| `fail-level` | `medium` | Minimum severity that triggers a non-zero exit. One of `note`, `fmt`, `low`, `medium`, `high`; an invalid value fails the gate with an explicit error. |
| `check-all` | `false` | Full scan (`--all`) instead of diff mode. |
| `no-fail` | `false` | Always exit 0; use for informational scans that must not block. |
| `upstream` | `''` | Base ref for diff comparison, e.g. `origin/main`. Required when `check-all` is false; ignored when it is true. |
| `timeout-minutes` | `15` | Job timeout in minutes. |

See `.github/workflows/python-qlty-gate.yml` for the authoritative input list.

## Required status check

The job inside the reusable workflow is named `Qlty Gate`. Callers must use the
job id `qlty-gate` so the resulting CheckRun is named `qlty-gate / Qlty Gate`.
That is the exact name to add to `required_status_checks` in the org baseline
ruleset, and it must match across repos for branch protection to resolve
consistently.
