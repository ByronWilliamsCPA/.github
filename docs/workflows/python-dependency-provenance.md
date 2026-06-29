# python-dependency-provenance.yml -- Deterministic Transitive Provenance

The `python-dependency-provenance.yml` reusable workflow makes Open-Source
vulnerability findings actionable by showing which DIRECT dependency introduces
each insecure TRANSITIVE package. It runs weekly, is fully deterministic and
keyless, and consumes no Anthropic API key and no hosted Snyk test quota. The
interpretation layer (deciding which fix to apply) runs locally on the
operator's subscription, separately from CI.

It complements the gating OSV-Scanner job in `python-sbom.yml`: that job blocks
merges on vulnerable dependencies; this workflow explains where each vulnerable
transitive package comes from so the fix targets the right direct dependency.

## What it runs

- `detect-config` - detects the ecosystem (Python `uv.lock` / `requirements*.txt`,
  frontend `package.json`) and whether to open the issue. Poetry is rejected
  (uv-only by org policy on the Python path).
- `provenance` - runs OSV-Scanner (keyless) to list vulnerable packages, then
  traces each one back to its introducing direct dependency with
  `uv tree --invert --package <pkg>` (Python, output tags the introducing extra
  such as `extra: dev`) and `npm why <pkg>` (frontend). Assembles a structured
  Markdown report and uploads it as a build artifact.
- `post-issue` - posts or updates a sticky GitHub issue (anchored by an
  HTML-comment marker) with the report, via the `gh` CLI. Tolerant of zero-vuln
  runs.
- `provenance-gate` - aggregates job results. It is a reporter, not a merge
  gate: it fails only when the report pipeline itself errored, never on the
  presence of vulnerabilities.

## Minimal usage

```yaml
jobs:
  provenance:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-dependency-provenance.yml@v1
    permissions:
      contents: read
      issues: write   # only the post-issue job needs this
    with:
      python-version: '3.12'
      open-issue: true
```

## Scheduled (weekly) usage

```yaml
name: Dependency Provenance

on:
  schedule:
    - cron: '23 6 * * 1'   # weekly, Monday 06:23 UTC (off-peak, non-:00)
  workflow_dispatch:

jobs:
  provenance:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-dependency-provenance.yml@v1
    permissions:
      contents: read
      issues: write
    with:
      python-version: '3.12'
      open-issue: true
```

## Inputs

| Input | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `python-version` | string | no | `3.12` | Python version for dependency resolution |
| `source-directory` | string | no | `src` | Source code directory hint (reserved; provenance reads the lockfile at repo root) |
| `lockfile` | string | no | `''` | Python lockfile hint (`uv.lock` or a `requirements*.txt`). Auto-detected when empty. |
| `frontend-directory` | string | no | `frontend` | Directory containing the frontend `package.json` |
| `open-issue` | boolean | no | `true` | Post/update the sticky GitHub issue. When false, only the artifact is produced. |
| `artifact-retention-days` | number | no | `90` | Days to retain the report artifact |
| `no-build` | boolean | no | `true` | Pass `--no-build` to `uv sync` (disable for projects with a build backend) |

## Secrets

None. The workflow uses the default `GITHUB_TOKEN` to open/update the issue and
consumes no third-party API key. It is token-optional by design: there is no
external token to omit.

## Caller permissions required

The caller must grant the following at the workflow or calling-job level:

- `contents: read`
- `issues: write`

Omitting `issues: write` causes the `post-issue` job to fail, because a called
workflow's token is bounded by the caller's permissions. Granting a scope the
callee does not need is also avoided: only the `post-issue` job carries
`issues: write`.

## Ecosystem detection

| Condition | Python state | Behaviour |
|-----------|--------------|-----------|
| `uv.lock` present (or hinted) | `uv-locked` | OSV scans `uv.lock`; provenance via `uv tree --invert` |
| `requirements*.txt` present, no `uv.lock` | `requirements` | OSV scans the requirements file; no `uv tree` graph |
| `poetry.lock` or `[tool.poetry]` | rejected | Errors out (uv-only by org policy) |
| none of the above | `skip` | Python path skipped |

| Condition | Frontend state | Behaviour |
|-----------|----------------|-----------|
| `frontend/package.json` present | `npm` | `npm audit` + `npm why` in `frontend/` |
| root `package.json` present | `npm-root` | `npm audit` + `npm why` at repo root |
| neither | `skip` | Frontend path skipped |

When neither ecosystem is detected, the report notes "no ecosystems scanned"
and the sticky issue records a clean cycle.

## Reading results

### The sticky issue

The report is posted as a single sticky GitHub issue whose first line is the
marker `<!-- dependency-provenance -->`. Each weekly run finds that issue by
the marker and updates it in place (adding a short "refreshed" comment), so the
issue history is one running thread rather than a new issue per week. A
zero-vuln run still updates the issue with a "no actionable transitive vulns
this week" body, so a clean cycle is observable rather than silent.

### The report table

| Column | Meaning |
|--------|---------|
| Vulnerability | OSV/GHSA id, with the CVE alias in parentheses when present |
| Severity | CRITICAL / HIGH / MEDIUM / LOW (from OSV group max severity or the database-specific label) |
| Vulnerable package | The insecure transitive (or direct) package |
| Introducing direct dep | The direct dependency that pulls the vulnerable package in |
| Extra/group | The introducing optional extra or dependency group (`(runtime)` when none) |
| Suggested action | Advisory category: `remove` / `upgrade` / `replace` / `gate` |

The **Suggested action** column is an advisory hint for the local
interpretation agent, not a decision:

- **remove** - the vulnerable package arrives only through an optional/dev extra
  or group; dropping that extra is often the cheapest fix.
- **upgrade** - a runtime direct dependency pulls it in; bump the direct
  dependency (or its transitive pin).
- **replace** - the vulnerable package IS a direct dependency; upgrade it
  directly or swap it out.
- **gate** - provenance could not be determined; investigate manually.

### The artifact

The same report is uploaded as the `dependency-provenance-report` artifact on
every run, regardless of `open-issue`, so the data is available even when issue
posting is disabled.

## Notes

- **Deterministic and keyless.** OSV-Scanner runs keyless, `uv tree` and
  `npm why` run locally against the committed lockfiles. No hosted-scanner quota
  is consumed and no Anthropic API key is used.
- **Reporter, not a gate.** This workflow never fails on the presence of
  vulnerabilities. The gating OSV-Scanner job in `python-sbom.yml` owns the
  merge gate.
- **uv-only on the Python path.** Poetry repos are rejected with an actionable
  error, matching `python-sbom.yml` and `python-snyk.yml`.
- **Role boundary.** Snyk owns SAST + IaC + AIBOM and keeps Open Source
  advisory; deterministic transitive-provenance reporting is handled by this
  workflow plus a local interpretation agent. See
  [ADR-003](../planning/adr/adr-003-snyk-ai-code-security.md) and
  ByronWilliamsCPA/.claude ADR-009.
