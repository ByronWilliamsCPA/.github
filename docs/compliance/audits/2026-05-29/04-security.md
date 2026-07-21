# 04 - Security and Secrets

HEAD e070932. Workflow security posture is strong: all 51 workflow files (`.github/workflows/*.yml` + `workflow-templates/*.yml`) carry a top-level `permissions:` block (37 use `permissions: {}` deny-by-default, the rest scoped), every third-party action is SHA-pinned except one template, no `pull_request_target` anywhere, no `secrets: inherit` (all callees take explicit `secrets:` blocks), and all untrusted `github.event.*` inputs reach `run:` steps through `env:` indirection rather than direct interpolation. No hardcoded secrets found in tracked files. One floating-tag action pin and one non-blocking SonarQube quality gate are the notable items; both live in `workflow-templates/` (cookiecutter-rendered, not consumed via `uses:`).

---

**SEC-01: Floating `@master` action pin in SonarQube quality-gate template**
Severity: Medium. Effort: S (one-line SHA pin once the intended release is chosen).
Evidence: `workflow-templates/python-sonarcloud.yml:103` `uses: sonarsource/sonarqube-quality-gate-action@master`. This is the only non-SHA, non-comment `uses:` across all 51 workflow files (confirmed by grep: every other `uses:` is a 40-char SHA, a local `./` reusable ref, or a commented usage example). It is a template rendered into downstream repos, not invoked here via `uses:`, so it does not affect this repo's own runs, but it propagates an unpinned mutable ref to every consumer. `@master` resolves to whatever the upstream default branch holds at run time: supply-chain exposure if that repo is compromised or force-pushed.
Recommendation: pin to the action's current release SHA with a trailing `# vX.Y.Z` comment, matching the convention used everywhere else in the repo.
CVE: n/a.

**SEC-02: SonarQube quality gate is non-blocking (`continue-on-error: true`)**
Severity: Low. Effort: S.
Evidence: `workflow-templates/python-sonarcloud.yml:108` `continue-on-error: true  # Don't fail workflow, just report status` on the "Check Quality Gate" step. A failing Sonar quality gate will not fail the workflow. This is an intentional report-only posture, but it means the gate cannot block a merge in consuming repos. Sonar coverage/quality is not a hard security gate (vuln gating is handled by `python-security-analysis.yml` / Trivy / dependency-review), so severity is Low.
Recommendation: document the report-only behavior in the template header, or expose an input so consumers can opt into blocking. No change required if report-only is the deliberate design.
CVE: n/a.

**SEC-03: Trivy/Hadolint SARIF-upload and DHI-login steps use `continue-on-error`, but the vuln gate itself is preserved**
Severity: Low. Effort: S (verify intent only).
Evidence: `.github/workflows/python-container-security.yml:168` (Hadolint SARIF upload), `:216` (DHI login), `:286` (Trivy SARIF upload) all set `continue-on-error: true`. These suppress failures on SARIF *upload* and registry *login*, not on detection. The actual vuln gate is `:269` `exit-code: ${{ inputs.fail-on-vulnerabilities && '1' || '0' }}` on the Trivy scan step (no continue-on-error), so a vuln finding still fails the job when `fail-on-vulnerabilities` is true. Note the gate is opt-in: if a consumer leaves `fail-on-vulnerabilities` false, Trivy runs in report-only mode (exit-code 0). The scorecard `continue-on-error: true` at `python-scorecard.yml:124` is justified inline (action v2.4.3 orphan-upload bug) and is immediately followed by a "Verify SARIF was generated" hard-fail step, so detection is not silently lost.
Recommendation: confirm the default of `fail-on-vulnerabilities` matches the intended posture for consumers; consider defaulting it to true so the container gate blocks unless explicitly waived.
CVE: n/a.

**SEC-04: Reusable security/scorecard workflows referenced by mutable `# main` comment despite SHA pin**
Severity: Low. Effort: S.
Evidence: `.github/workflows/security-analysis.yml:23` and `.github/workflows/scorecard.yml:29` both pin the org reusable workflow to SHA `6f71aecae2c91214ca0a0a2206a36cf912aa31ac` with a trailing `# main` comment. The SHA pin is correct and immutable; the concern is process: the `# main` comment signals these track a branch, so an automated bump tool could advance the SHA to whatever `main` points to without a release-tag gate. Functionally safe today (it is a SHA), but it bypasses any tag/version review for this repo's own security gates.
Recommendation: once the repo cuts versioned tags, repin self-referential security workflows to a `# vX` tag SHA so the org's own gates ride released code, not branch tip.
CVE: n/a.

**SEC-05: No live dependency vulnerability scan possible in this audit**
Severity: Informational. Effort: n/a.
Evidence: `docs/known-vulnerabilities.md` lists zero open CVEs ("No known vulnerabilities as of 2026-05-14") and notes the repo ships no Python package and no container images, so there is no dependency manifest to scan. detect-secrets/trufflehog/trivy/pip-audit are not installed and there is no network, so I could not run a live scan. The tracked file is consistent (FOUND-007 placeholder, reassessment cadence documented). Claim cannot be independently verified here.
Recommendation: rely on the CI `pip-audit`/Trivy toolchain for live results; no action from this static audit.
CVE: none claimed.

---

## Clean sub-areas (one line each)

- Hardcoded secrets: none. Broad grep for AWS keys (`AKIA`), PEM private-key headers, `ghp_`/`github_pat_`, `xox*`, `AIza*`, inline passwords across all tracked files returned nothing (all `secrets.*` references are `${{ secrets.NAME }}` GitHub expressions).
- `.secrets.baseline`: clean, no drift. 6 entries across 2 files (`python-scorecard.yml:106` Secret Keyword; `.pre-commit-config.yaml:8/25/34/43/52` Hex High Entropy String); both files exist, line counts (211 / 92) comfortably cover all referenced line numbers, all entries `is_verified=false` and are pre-commit-hook revision SHAs / pragma-allowlisted token-presence checks, not real secrets.
- `.trufflehog-exclude`: minimal and reasonable scope (`CHANGELOG.md`, `\.submodules/`); does not mask source or workflow files.
- `checksums.txt`: 10 entries, community-health docs only; not a secret surface.
- Top-level `permissions:` coverage: 51/51 workflow files have one; 37 use `permissions: {}` deny-all default. No `write-all`. The three `read-all` instances (`workflow-templates/python-security-analysis.yml:50`, `python-publish-pypi.yml:30`, `python-codecov.yml:25`) are read-only top-level scopes with narrower per-job grants, which is acceptable.
- Script injection: none. All untrusted `github.event.*` values (PR title `pr-validation.yml:32`, PR body `:59`, workflow_run head branch/sha/owner `python-release.yml:255/280/285`, fork repo `python-docker.yml:233`) are passed via `env:` and referenced as `"$VAR"` inside `run:`, not interpolated into the shell. No `${{ github.event.* }}` appears directly inside a run-script command body.
- Dangerous triggers: no `pull_request_target` anywhere. `workflow_run` handling in `python-release.yml` guards with a fork-owner check (`:252-260` refuses when `head_repository.owner != repository_owner`) before checkout. `python-release.yml`/`python-docker.yml` `on:` are `workflow_call` only (downstream caller controls triggers). `workflow-templates/python-codecov.yml` documents the `workflow_run` pwn-request avoidance and does not check out PR code.
- `secrets:` propagation: no `secrets: inherit`. Every reusable callee declares explicit `secrets:` inputs; tokens (`SONAR_TOKEN`, `CODECOV_TOKEN`, `QLTY_COVERAGE_TOKEN`, `SCORECARD_TOKEN`, `DHI_USERNAME`/`DHI_PAT`) are passed by name only.
- Insecure shell in `scripts/*.sh`: none security-relevant. No `eval`, no `curl|bash`, no predictable temp files (all temp files use `mktemp`). `scripts/sync-secrets.sh` reads the secret value with `read -rs` (hidden), passes it via `--body "$SECRET_VALUE"` (quoted) to `gh secret set`, and runs `set -euo pipefail`; the value transits the process argv but the script is an interactive admin tool, not a CI step.
- Security gates blocking: `codeql.yml`, `dependency-review.yml` (`fail-on-severity: high`), `security-analysis.yml` (has a `security-gate-validation` job that hard-fails if the scan result != success) have no continue-on-error on detection steps.
- `SECURITY.md`: coherent. Defines reporting channel, coordinated disclosure, supported-versions table, and concrete SLAs (5-day ack, 2-day critical triage, 14-day critical fix). No accuracy red flags at a high level.

---

## Backlog rows (for orchestrator)

| ID | title | domain | severity | effort | files | evidence | recommendation | cve |
|----|-------|--------|----------|--------|-------|----------|----------------|-----|
| SEC-01 | Floating `@master` action pin in SonarQube quality-gate template | security | Medium | S | workflow-templates/python-sonarcloud.yml | line 103 `uses: sonarsource/sonarqube-quality-gate-action@master` (only non-SHA uses across 51 files) | Pin to release SHA with `# vX.Y.Z` comment | n/a |
| SEC-02 | SonarQube quality gate non-blocking | security | Low | S | workflow-templates/python-sonarcloud.yml | line 108 `continue-on-error: true` on Check Quality Gate | Document report-only intent or add opt-in blocking input | n/a |
| SEC-03 | Container scan SARIF/login steps use continue-on-error; vuln gate opt-in | security | Low | S | .github/workflows/python-container-security.yml | lines 168/216/286 continue-on-error; gate at 269 `exit-code` keyed on fail-on-vulnerabilities | Confirm/flip default of fail-on-vulnerabilities to true | n/a |
| SEC-04 | Self-referential security workflows pinned via mutable `# main` comment | security | Low | S | .github/workflows/security-analysis.yml, .github/workflows/scorecard.yml | lines 23 / 29 SHA `6f71aec...` `# main` | Repin to released `# vX` tag SHA once tags exist | n/a |
| SEC-05 | No live dependency vuln scan possible (no network/tools) | security | Info | n/a | docs/known-vulnerabilities.md | "No known vulnerabilities as of 2026-05-14"; no pkg/image to scan | Rely on CI pip-audit/Trivy for live results | none |
