# python-snyk.yml -- Snyk AI Code Security Layer

The `python-snyk.yml` reusable workflow adds a Snyk AI-code-security layer to a
Python repository: Snyk Code (SAST), an advisory Snyk Open Source (SCA) cross-check,
and an AI-BOM inventory. It complements the existing OSV plus Renovate SCA stack; it
does not replace it. The workflow is opt-in and token-gated, and it no-ops cleanly
when `SNYK_TOKEN` is absent.

## What it runs

- `detect-config` - checks for `SNYK_TOKEN` and detects repo state (uv-locked, uv-no-lock, poetry-not-supported, or skip)
- `snyk-code` - Snyk Code (SAST); cross-file dataflow analysis, uploads SARIF to the Security tab
- `snyk-oss` - Snyk Open Source (SCA cross-check); advisory and `continue-on-error`, never fails the build
- `snyk-aibom` - generates a CycloneDX AI-BOM and uploads it as a build artifact
- `snyk-gate` - aggregates results; gates on Snyk Code only (OSS is advisory and excluded from the decision)

## Minimal usage

```yaml
jobs:
  snyk:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-snyk.yml@v1
    permissions:
      contents: read
      security-events: write   # SARIF upload to the Security tab
    with:
      source-directory: 'src'
      run-code: true           # Snyk Code (SAST)
      run-oss: false           # SCA cross-check (OSV/Renovate are primary)
      run-aibom: false         # AI-BOM (set true for LLM/RAG/MCP repos)
      fail-on-high: true
    secrets:
      SNYK_TOKEN: ${{ secrets.SNYK_TOKEN }}
```

## Inputs

| Input | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `source-directory` | string | no | `src` | Source code directory to scan |
| `python-version` | string | no | `3.12` | Python version for dependency resolution |
| `run-code` | boolean | no | `true` | Run Snyk Code (SAST) |
| `run-oss` | boolean | no | `false` | Run Snyk Open Source (SCA cross-check); advisory, OSV/Renovate are primary |
| `run-aibom` | boolean | no | `false` | Generate an AI-BOM (Python only; for LLM/RAG/MCP repos) |
| `fail-on-high` | boolean | no | `true` | Fail the build on HIGH/CRITICAL Snyk Code findings |
| `no-build` | boolean | no | `true` | Pass `--no-build` to `uv sync` (disable for projects with a build backend) |

## Secrets

| Secret | Required | Purpose |
|--------|----------|---------|
| `SNYK_TOKEN` | no | Snyk API token. When absent, all scan jobs no-op. |

## Caller permissions required

The caller must grant the following at the workflow or calling-job level:

- `contents: read`
- `security-events: write`

Omitting `security-events: write` causes a startup failure (`startup_failure` /
generic "workflow file issue") before any job runs, because a called workflow's
token is bounded by the caller's permissions.

## Operator setup

1. **Create the Snyk account, org, and token.** Create a Snyk account, create one
   Snyk Organization (a CI token reports to its org regardless of repo owner, so one
   org covers both GitHub owners on Free), and generate a service token.

2. **Set the secret.** Mirror the existing `SONAR_TOKEN` pattern: an org-level secret
   for ByronWilliamsCPA and a repo-level secret for williaby personal repos.

   ```bash
   # ByronWilliamsCPA org repos (visibility: all)
   gh secret set SNYK_TOKEN --org ByronWilliamsCPA --visibility all

   # williaby personal repos
   ./scripts/sync-secrets.sh
   ```

3. **Configure the Snyk MCP server in Claude Code.** This enables agent-loop scanning
   inside the coding agent.

   ```bash
   npx -y snyk@latest mcp configure --tool=claude-cli
   snyk auth
   ```

4. **AI-BOM usage.** Generate an AI-BOM locally, or wire it into CI through a direct
   caller.

   ```bash
   # Local
   snyk aibom --json > aibom.json
   ```

   In CI, set `run-aibom: true` in a direct caller of `python-snyk.yml`.

## Notes

- **uv-only.** This workflow is uv-only by org policy. Poetry repos are rejected with
  an actionable error.
- **Snyk SCA does not parse `uv.lock`.** The OSS job exports the committed lockfile to
  a requirements file Snyk understands, and runs only in the `uv-locked` state so it
  never triggers a live network resolve.
- **OSS is advisory and default-off.** OSV plus Renovate remain the primary SCA gate;
  the OSS job is `continue-on-error` and is excluded from the gate decision.
- **AI-BOM** is enabled via `enable-aibom: true` in `python-standard-stack.yml`
  (requires `run-snyk: true` and `SNYK_TOKEN`), or by setting `run-aibom: true`
  in a direct caller of this workflow.

## Reading Results

### Snyk Code (SAST)

SARIF results appear in the repository's Security tab under Code Scanning. Each
finding includes:

- **Severity**: CRITICAL, HIGH, MEDIUM, or LOW, based on Snyk's CVSS scoring
- **Rule**: the Snyk Code rule that fired (e.g., `javascript/SQLInjection`)
- **Data flow**: for cross-file findings, a path from source to sink

### Snyk Open Source (SCA)

When `run-oss: true`, `snyk test --json` output includes exploit maturity fields
on any paid Snyk plan:

- `isExploitable` (boolean): `true` when a public PoC or in-the-wild exploit exists
- `exploitMaturity`: one of `No Known Exploit`, `Proof of Concept`, `Functional`,
  or `Mature`

These fields are the primary reason to run the OSS job even when Renovate is the
fix-PR source: Snyk surfaces vulnerabilities in the pre-NVD window (days to weeks
before CVE assignment) and labels them as exploitable before NVD data is available.
Renovate's advisories trail NVD by design, so a Snyk OSS finding with
`exploitMaturity: Functional` and no CVE yet is a genuine early-warning signal worth
acting on rather than waiting for a Renovate fix-PR.

Results appear in the Snyk dashboard (app.snyk.io) under the connected project, not
in the GitHub Security tab (OSS findings are not uploaded as SARIF).

See [ADR-003](../planning/adr/adr-003-snyk-ai-code-security.md) for the adoption
rationale.
