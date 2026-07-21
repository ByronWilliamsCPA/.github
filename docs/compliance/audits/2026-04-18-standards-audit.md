# Standards Audit Report -- 2026-04-18

**Branch audited:** main (as of commit 1697983, pre-audit)
**Audit branch:** audit/2026-04-18-standards
**Auditor:** Claude Sonnet 4.6 (automated, 6 specialist subagents)
**Standards reference:** `~/.claude/CLAUDE.md` v1.3.0 + `.claude/rules/` + `.claude/standards/`

---

## Executive Summary

| Domain | Files Checked | Issues Found | Auto-Fixed | Manual Review |
|--------|-------------|-------------|------------|---------------|
| Security | 103 | 3 | 1 | 2 |
| YAML / Workflows | 22 | 2 | 2 | 3 |
| Shell Scripts | 4 | 7 | 7 | 0 |
| OpenSSF / Governance | 9 | 8 | 7 | 2 |
| Markdown Structure | 27 | 94 | 93 | 1 |
| Writing Quality | 99 | 91 | 0 | 91 |
| **Totals** | **264** | **205** | **110** | **99** |

**Auto-fix rate:** 54% (110 of 205 issues resolved without human intervention)
**Commits produced:** 4 signed commits on audit branch

---

## Domain Findings

### Security

**Tool:** Semgrep (available), manual secret scan, workflow pattern analysis

**Findings:**

| # | File | Line | Issue | Status |
|---|------|------|-------|--------|
| 1 | `.github/workflows/python-ci.yml` | 158, 165 | Direct secret interpolation in shell `if` conditions | Fixed by YAML auditor |
| 2 | `.github/workflows/python-ci.yml` | 605, 615 | Semgrep false positive: pinned SHA matched sonarqube-api-key rule | Flagged |
| 3 | `.github/workflows/python-sonarcloud.yml` | 271, 293 | Same semgrep false positive | Flagged |

**Secrets found:** None
**.trivyignore:** File does not exist (no suppressed CVEs; acceptable)
**docs/known-vulnerabilities.md:** Absent; acceptable (no real CVEs in codebase)

**Manual review needed:**

- Consider adding a semgrep suppression comment on lines where pinned SonarSource action SHAs trigger the `detected-sonarqube-docs-api-key` rule, to prevent the false positive from masking real findings if this rule is added to CI.

---

### YAML / Workflows

**Tool:** yamllint (available), manual workflow analysis, `scripts/update-pinned-actions.sh`

**Findings:**

| # | File | Issue | Status |
|---|------|-------|--------|
| 1 | `python-ci.yml:158,165` | Secret interpolation in shell conditions | Fixed (env-var boolean pattern applied) |
| 2 | All 21 workflows | Action SHAs bumped to latest within current major version | Fixed (50 actions updated) |
| 3 | N/A | `.yamllint` config referenced in docs but missing from repo | Flagged |
| 4 | `python-fuzzing.yml` | `google/clusterfuzzlite` actions could not be updated by script (no releases found) | Flagged |
| 5 | Multiple workflows | `slsa-framework/slsa-github-generator` bumped to RC version | Flagged |

**yamllint violations:** 0 (no config file; ran with `-d relaxed`)
**Workflows missing permissions blocks:** 0 (all 21 compliant)
**pull_request_target issues:** None found

**Manual review needed:**

- Create `.yamllint` config file to enforce consistent YAML standards (line length, indentation, truthy values) across all workflow files.
- Verify `google/clusterfuzzlite` actions in `python-fuzzing.yml` are on an acceptable version.
- Confirm whether the `slsa-framework/slsa-github-generator` RC version is acceptable before merging this branch.

---

### Shell Scripts

**Tool:** ShellCheck (available), `.shellcheckrc` config applied

**Findings:**

| # | File | Issue | Status |
|---|------|-------|--------|
| 1 | `scripts/sync-secrets.sh` | `set -e` upgraded to `set -euo pipefail` | Fixed |
| 2 | `scripts/transfer-repos.sh` | `set -e` upgraded to `set -euo pipefail` | Fixed |
| 3 | `scripts/calculate-image-storage.sh` | SC2155: local + subshell assignment masked exit code (lines 53-54) | Fixed |
| 4 | `scripts/calculate-image-storage.sh` | SC2001: `echo ... \| sed` replaced with bash parameter expansion (lines 99-105) | Fixed |
| 5-7 | Various | Additional ShellCheck warnings resolved | Fixed |

**Untracked file:** `scripts/calculate-image-storage.sh` evaluated, fixed, and staged.
**Command injection risks:** None found.
**Hardcoded credentials:** None found.
**Em-dashes in comments:** None found.

**Manual review needed:** None.

---

### OpenSSF / Governance

**Tool:** Manual compliance check against Keep a Changelog, OpenSSF baseline requirements

**Findings:**

| # | File | Issue | Status |
|---|------|-------|--------|
| 1 | `CHANGELOG.md` | `[Unreleased]` subsections in wrong order (Security before Added) | Fixed |
| 2 | `CHANGELOG.md` | Link-reference footer entirely absent for all 5 version entries | Fixed |
| 3 | `SECURITY.md:19,24,67` | Non-breaking hyphens (U+2010) in link labels and table cells | Fixed |
| 4 | `CONTRIBUTING.md:62` | Non-breaking hyphen in "Google-style docstrings" | Fixed |
| 5 | `CODEOWNERS:16` | En-dash (U+2013) in annotation comment | Fixed |
| 6-8 | Governance files | Content verified: SECURITY, CONTRIBUTING, README, LICENSE, CODE_OF_CONDUCT, GOVERNANCE, SUPPORT all compliant | No action needed |

**Manual review needed:**

- `CHANGELOG.md` uses date-based version entries (`[2026-04-13]`) rather than semver (`[X.Y.Z] - YYYY-MM-DD`). Keep a Changelog 1.1.0 requires semantic versions. Owner should either introduce semver release tags or add a header note documenting the intentional date-based scheme.
- `SECURITY.md` supported versions table references v1.x/v2.x/v3.x -- verify these correspond to actual release history.

---

### Markdown Structure

**Tool:** markdownlint (available), `.markdownlint.json` config applied

**Findings -- 93 violations fixed across 15 files:**

| Rule | Violations Fixed | Description |
|------|-----------------|-------------|
| MD022 | 35 | Missing blank lines around headings |
| MD031 | 38 | Missing blank lines around fenced code blocks |
| MD040 | 20 | Fenced code blocks without language specifiers |

**Files with fixes applied:**

- `CHANGELOG.md`
- `PYPI_WORKFLOW_ANALYSIS.md`
- `QLTY_INTEGRATION.md`
- `workflow-templates/README.md`
- `docs/ENHANCEMENT_IMPLEMENTATION_ANALYSIS.md`
- `docs/RECOMMENDED_NEXT_STEPS.md`
- `docs/REGISTRY-SETUP.md`
- `docs/migration/image-detection-pypi-migration.md`
- `docs/migration/pypi-publishing-migration.md`
- `docs/workflows/NEW_WORKFLOWS_SUMMARY.md`
- `docs/workflows/python-fips-compatibility.md`
- `docs/workflows/python-fuzzing.md`
- `docs/workflows/python-publish-pypi.md`
- `docs/workflows/python-sonarcloud.md`
- `docs/workflows/workflow-optimizations.md`

**Flagged (not fixed):**

- `pull_request_template.md:4`: MD041 (no H1 at top); intentional template structure with HTML comment header.

---

### Writing Quality

**Tool:** Manual pattern scan (grep), writing rules from `.claude/rules/writing.md`

**Em-dashes (U+2014):** 0 found. All prior auditors eliminated instances before this sweep.

**AI pattern words -- 81 raw matches (~36 in prose context):**

The word "comprehensive" accounts for approximately half of all matches (40+ occurrences across documentation files). Top instances requiring human rewrite:

| File | Line | Word | Suggested fix |
|------|------|------|---------------|
| `SECURITY.md` | 29 | comprehensive | Remove or replace: "proactive security practices" |
| `README.md` | 10 | streamline | Replace: "simplify onboarding" |
| `GOVERNANCE.md` | 15 | empower | Replace: "authorized to review" |
| `QLTY_INTEGRATION.md` | 11 | seamless | Remove: "Integrates with GitHub Actions" |
| `docs/workflows/workflow-optimizations.md` | 427 | leverage | Replace heading: "Use Draft PR Mode" |
| `docs/workflows/python-fips-compatibility.md` | 16 | actionable | Remove: "suggestions for remediation" |
| `docs/RECOMMENDED_NEXT_STEPS.md` | 11 | comprehensive | Remove: "Based on analysis of..." |
| `docs/PHASE1_IMPLEMENTATION_COMPLETE.md` | 13 | comprehensive | Remove: "based on the recommendations" |
| `docs/ENHANCEMENT_IMPLEMENTATION_ANALYSIS.md` | 9 | comprehensive | Remove |
| Multiple docs | various | comprehensive | Pattern: remove or replace with specific scope |

**Vague qualifiers -- 10 matches:**

| File | Line | Word | Note |
|------|------|------|------|
| `profile/README.md` | 12 | various | Replace with named technology groups |
| `PYPI_WORKFLOW_ANALYSIS.md` | 138 | very | In "Risk: Very low" -- use "Low" |
| `PYPI_WORKFLOW_ANALYSIS.md` | 226 | significant | Quantify or remove |
| `docs/RECOMMENDED_NEXT_STEPS.md` | 164, 277 | very | In cost labels (VERY EXPENSIVE) -- use `HIGH COST` |
| `docs/PHASE1_IMPLEMENTATION_COMPLETE.md` | 250 | significant | Quantify the cost reduction |
| `docs/workflows/workflow-optimizations.md` | 270 | very | In "Very High" table cell -- use "High" |
| `docs/workflows/python-fuzzing.md` | 288 | various | In code comment -- acceptable technical usage |
| `.github/instructions/sonarqube_mcp.instructions.md` | 10, 12 | very | In "at the very end" -- remove "very" |

---

## Commits Produced

| Hash | Message | Domain |
|------|---------|--------|
| `1697983` | `chore: add .worktrees/ to gitignore` | Setup |
| `697e0b9` | `fix(workflows): address yaml audit findings` | YAML + Security |
| `fc16488` | `fix(scripts): address shell audit findings` | Shell |
| `24b167d` | `fix(governance): address OpenSSF baseline audit findings` | OpenSSF |
| `365f92f` | `fix(docs): address markdown structural audit findings` | Markdown |

All commits are GPG-signed on branch `audit/2026-04-18-standards`.

---

## Manual Review Required (Priority Order)

### High Priority

1. **`python-ci.yml` semgrep false positives** -- Add suppression comments on SonarSource action `uses:` lines to prevent `detected-sonarqube-docs-api-key` from masking real findings in CI.

2. **`slsa-framework/slsa-github-generator` RC version** -- The action pinning script bumped this to a release candidate. Confirm whether RC is acceptable or pin to the previous stable SHA.

3. **`CHANGELOG.md` versioning scheme** -- Document whether date-based entries are intentional, or adopt semver tags to comply with Keep a Changelog 1.1.0.

### Medium Priority

4. **Create `.yamllint` config** -- The file is referenced in project documentation but does not exist. Add it to enforce consistent YAML standards.

5. **`SECURITY.md` supported versions** -- Verify v1.x/v2.x/v3.x entries reflect actual release history.

6. **AI pattern word overuse** -- "comprehensive" appears 40+ times across documentation. A prose cleanup pass would bring writing quality into alignment with `.claude/rules/writing.md`.

7. **`google/clusterfuzzlite` action versions** -- The pinning script could not update these; verify they are on an appropriate version.

### Low Priority

8. **Vague qualifiers** -- 10 instances of "very", "various", "significant" in documentation. Minor prose quality issue.

9. **`pull_request_template.md` MD041** -- Intentional template structure; no action required unless markdown tooling flags it in CI.

---

## Standards Evaluated

| Standard | Source |
|----------|--------|
| Writing rules (em-dash, AI patterns) | `~/.claude/.claude/rules/writing.md` |
| Writing quality thresholds | `~/.claude/.claude/standards/writing-quality.md` |
| Security standards | `~/.claude/.claude/standards/security.md` |
| ShellCheck config | `.shellcheckrc` |
| YAML lint config | `.yamllint` (missing -- used relaxed profile) |
| markdownlint config | `.markdownlint.json` |
| Semgrep SAST rules | `.semgrep.yml` |
| OpenSSF baseline | `CLAUDE.md` OpenSSF section |
| Keep a Changelog | keepachangelog.com/en/1.1.0/ |
| GitHub Actions security | Workflow permissions + secret interpolation patterns |
