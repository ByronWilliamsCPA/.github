# Changelog

All notable changes to this project's shared workflow templates are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

This project uses date-based version headers (e.g. `[2025-01-07]`) rather than
semver because it is a shared workflow library with continuous deployment; there
are no numbered releases.

## [Unreleased]

### Added

- All 11 reusable Python workflows: `no-build` boolean input (default `true`) controls whether `--no-build` is passed to `uv sync`/`uv run` commands; allows repos with a build backend (hatchling, setuptools) to opt out of the flag that prevented local package installation; routed through a job-level `NO_BUILD_FLAG` env var so callers need only set `no-build: false` in their `with:` block
- `SECURITY.md`: Security Surface Areas section documenting the threat model for this workflow library
- `python-precommit.yml`: new reusable workflow that runs `pre-commit run --all-files` in the project virtualenv via `uv run`; inputs `config-path`, `python-version`, `fail-fast`; all inputs via env vars; SHA-pinned actions
- `python-standard-stack.yml`: new composite reusable workflow chaining `python-ci.yml`, `python-security-analysis.yml`, and `python-sbom.yml` via `needs:`; recommended quickstart for new repos; exposes `python-version`, `source-directory`, `coverage-threshold`, `fail-on-high`; optional `SONAR_TOKEN`/`CODECOV_TOKEN` passthroughs
- `python-supplemental-checks.yml`: `enable-commit-lint` input (default false) that validates PR titles against Conventional Commits format via SHA-pinned `amannn/action-semantic-pull-request`; commit-lint status added to supplemental summary
- `python-scorecard.yml`: `min-score` input (type: number, default 0 = gate disabled) and `Evaluate Scorecard Scores` step that parses SARIF output and fails CI if any of Branch-Protection, Code-Review, Dangerous-Workflow, Token-Permissions, or Pinned-Dependencies scores below the threshold
- `scripts/update-pinned-actions.sh`: developer tool to scan workflow files for outdated pinned action SHAs and propose or apply updates within the same major version
- `CHANGELOG.md`: required OpenSSF baseline file
- Actionlint static analysis for GitHub Actions workflows via `.qlty/qlty.toml`
- `.yamllint` configuration file for YAML style enforcement
- `tests/update-pinned-actions.bats`: 38 automated tests covering dry-run, apply mode, annotated tag resolution, and sandbox PATH validation for the action-pinning script
- `tests/libs/bats-core`, `tests/libs/bats-support`, `tests/libs/bats-assert` submodules for test infrastructure
- `.github/workflows/shell-tests.yml`: CI workflow that runs bats tests on pushes and pull requests touching `scripts/`, `tests/`, or the workflow file itself
- `.pre-commit-config.yaml`: five new SHA-pinned pre-commit hooks: commitizen at `commit-msg` stage (PC-008), yamllint (PC-009), markdownlint-cli (PC-010), no-em-dash guard (PC-011), and detect-secrets (PC-013); all `rev:` values are 40-character commit SHAs
- `.cz.toml`: commitizen conventional commits configuration with `allow_abort = true` to permit merge and revert commit messages
- `.yamllint.yml`: yamllint config extending default with `document-start: disable`, relaxed line-length (150-char, warning) and truthy (warning) rules
- `.markdownlint.yml`: markdownlint config disabling 14 rules with pre-existing violations; MD060 (table-column-style) suppresses violations across USAGE_EXAMPLES.md, AGENTS.md, and docs/workflows/
- `scripts/check-no-em-dash.sh`: byte-sequence grep hook that blocks em-dash (U+2014) characters in staged text files; uses `language: script` with `types: [text]` to skip binary files
- `.secrets.baseline`: detect-secrets baseline with 5 SHA-pin false positives in `.pre-commit-config.yaml`
- `scorecard.yml`: add `self-scorecard` direct job with `publish_results: true` and `id-token: write`; runs `ossf/scorecard-action` without the reusable wrapper so the OIDC token `repository` claim resolves to `ByronWilliamsCPA/.github` (see ADR-001); includes SCORECARD_TOKEN guard, harden-runner, and job summary step
- `.codecov.yml`: Codecov configuration for `ByronWilliamsCPA/.github` with 80% project and 90% patch coverage targets

### Changed

- `python-ci.yml`: remove `check-secrets` job, `sonarcloud-quality-gate` job, and 7 Codecov upload/analytics steps; use `python-sonarcloud.yml` and `python-codecov.yml` directly for those integrations
- `python-ci.yml`: replace `safety` with `uvx`-free `uv run pip-audit` for dependency vulnerability scanning (CLAUDE.md standard); add `-c pyproject.toml` flag to bandit
- `python-ci.yml`: simplify `ci-gate` from 5-job to 3-job dependency (`quality-checks`, `llm-governance`, `matrix-testing`)
- `python-supplemental-checks.yml`: replace PR-title string parsing for major/minor/patch classification with label-based detection (`major`, `minor`, `patch`, `semver:*`, `version-update:semver-*` labels) -- not spoofable via title text
- `python-pr-validation.yml`: replace 7-job implementation with single hard-fail migration stub; callers must migrate to `python-ci.yml` and `python-supplemental-checks.yml` (breaking change)
- Rename `ci-summary` to `CI Gate` in `python-ci.yml`; upgrade from passive summary to active gate that fails when required upstream jobs (`quality-checks`, `llm-governance`) fail or are cancelled; optional jobs (`sonarcloud-quality-gate`, `matrix-testing`) pass when skipped
- Rename `Security Gate` to `Security Gate Validation` in `python-security-analysis.yml` to match CI-015 branch protection context
- Rename `Validation Summary` to `Dependency & Standards Validation` in `python-pr-validation.yml` to match CI-016 branch protection context
- Align `workflow-templates/python-security-analysis.yml` job display names with renamed check context
- Replace em-dash with semicolon in `SUPPORT.md`
- Prose cleanup across 18 documentation files to remove AI-pattern language and improve plain-language clarity
- `python-scorecard.yml`: add `Warn on deprecated publish-results input` step that emits a `::warning::` annotation when a caller passes `publish-results: true`; surfaces the deprecation in CI logs so callers know to remove the now-ignored input
- `.github/workflows/pr-validation.yml`: add `Dependency & Standards Validation` job to satisfy the required branch protection check context that no workflow in this repo was previously reporting; gates on the same title-check and body-check results as `PR Validation Gate`
- `.claude/CLAUDE.md`: project-scoped Claude Code instructions with Model Selection table, RAD tagging rules, no-em-dash writing rule, and git workflow conventions (CLAUDE-001 through CLAUDE-006)
- `.claude/settings.json`: explicit allow/deny permission block scoping Claude Code operations to safe repo commands (CLAUDE-002)
- `AGENTS.md`: agent catalog and model assignment table for subagents operating in this repo (CLAUDE-003)
- `GEMINI.md`: Gemini CLI context stub with repo summary, writing rules, and branch naming convention (CLAUDE-004)
- `docs/known-vulnerabilities.md`: empty CVE baseline satisfying the OpenSSF FOUND-007 foundation check; no known vulnerabilities as of 2026-05-14
- `docs/architecture/adr-000-index.md`, `docs/architecture/adr-001-scorecard-publish-results.md`: ADR infrastructure and first decision record documenting the `publish-results: false` constraint in the reusable scorecard workflow and the plan for a direct `self-scorecard` job (FOUND-008)
- `.gitignore`: narrow `.claude/` exclusion from directory-level to specific transient subdirs so `.claude/CLAUDE.md` and `.claude/settings.json` are tracked by git

### Fixed

- `workflow-templates/python-fips-compatibility.yml`: correct `uses:` path from `ByronWilliamsCPA/.github/workflows/python-fips-compatibility.yml` to `ByronWilliamsCPA/.github/.github/workflows/python-fips-compatibility.yml`; the previous single-`.github` path 404'd at runtime for any consumer copying this starter template; aligns with the doubled-`.github` pattern used by all other `workflow-templates/*.yml` callers
- `workflow-templates/python-cifuzzy.yml`: tighten the `github/codeql-action/upload-sarif` SHA tag comment from `# v4` to `# v4.35.4` to match the tag that resolves to the pinned SHA `68bde559dea0fdcac2102bfdf6230c5f70eb485e`
- `python-sbom.yml`, `python-publish-pypi.yml`, `python-reuse.yml`, `python-supplemental-checks.yml`: ensure a virtual environment exists before `uv pip install --no-build` runs; `uv pip install` operates on an existing `.venv` and does not create one automatically, so the first `Install` step failed in any downstream consumer with: `error: No virtual environment found`. `python-sbom.yml` swaps the existing `uv sync --frozen` step ahead of the `cyclonedx-bom` install; the other three workflows had no `uv sync` step and add a `uv venv` step (or run-block prefix) to materialise a bare venv before the tool install; observed in `ByronWilliamsCPA/gleif` PR #37 for the sbom workflow; fixes #106
- `python-performance-regression.yml`: fix `$NO_BUILD_FLAG` reference in the `Post PR Comment` step; the flag appeared as a literal string in the PR body because the step uses `actions/github-script` (JavaScript), not bash; add `NO_BUILD_FLAG` to the step `env:` block and use `${noBuildFlag}` (via `process.env.NO_BUILD_FLAG`) in the template literal
- `python-scorecard.yml`: replace `if: ${{ secrets.SCORECARD_TOKEN == '' }}` guard with an env-var + shell check pattern (`[ -z "$HAS_SCORECARD_TOKEN" ]`); direct secret comparison in `if:` expressions is unreliable in GitHub Actions (runner issue #520) because secrets are redacted before expression evaluation
- `python-compatibility.yml`: add `shell: bash` to the `Install dependencies` step to prevent silent failure on Windows matrix legs where the default shell is PowerShell and `$NO_BUILD_FLAG` expands to nothing
- `python-slsa.yml`, `python-standard-stack.yml`, `scorecard.yml`, `security-analysis.yml`: remove `timeout-minutes` from 6 reusable-workflow-call jobs (`provenance`, `ci`, `security`, `sbom`, `scorecard`); GitHub Actions disallows `timeout-minutes` on jobs that use `uses:`, causing actionlint CI failure
- `python-scorecard.yml`: hard-code `publish_results: false` in the `ossf/scorecard-action` step and remove `id-token: write` from the workflow permissions; the OIDC token `repository` claim resolves to the `.github` org repo when the workflow runs as a reusable callee, causing scorecard-action to publish to the wrong repository and error; the `publish-results` input is retained for backwards compatibility but is now deprecated and always treated as false; SARIF upload to the Security tab is unaffected
- `scorecard.yml`: remove `publish-results: true` and `id-token: write` from the `.github` org repo's own scorecard caller to align with the reusable workflow fix
- `workflow-templates/python-scorecard.yml`: remove `id-token: write` from top-level and job-level permissions and remove `publish-results: true` from the `with:` block; aligns the starter template with the reusable workflow fix so new repos generated from this template get the correct permission set
- `python-compatibility.yml`: move `# shellcheck disable=SC1033,...` directives from YAML-level comments into the `run: |` block body for the Ubuntu and macOS system-deps steps; shellcheck only processes content inside the run block, so YAML-level disable comments were silently ignored, causing the self-test CI to fail on shellcheck SC1073/SC1033/SC1050/SC1072/SC1140
- `python-compatibility.yml`: extract package-name regex into a `pkg_pattern` variable for the Ubuntu and macOS system-deps steps; shellcheck cannot parse bracket-class regex (`[a-zA-Z0-9_\-\. ]`) inline in `[[ =~ ]]` expressions and reports SC1073/SC1033/SC1050/SC1072/SC1140; using an unquoted variable reference causes shellcheck to treat the value as an opaque string and skip regex parsing; fixes pre-existing self-test CI failure introduced in #77
- `python-publish-pypi.yml`: install `pip-audit==2.10.0` and `bandit[toml]==1.9.4` via `uv pip install --no-build` and invoke them directly; an earlier approach using `uv run --with` was superseded when SonarCloud S8541 flagged it for arbitrary build-script execution risk; see the Security section for the current remediation
- Fix stale `williaby` org reference in usage example comments for `python-fuzzing.yml`, `python-performance-regression.yml`, and `python-qlty-coverage.yml`
- Add `timeout-minutes: 5` to `build-matrix` and `compatibility-summary` jobs in `python-compatibility.yml`
- Add `timeout-minutes: 5` to `check-configuration` jobs in `python-sonarcloud.yml` and `python-qlty-coverage.yml`
- `scripts/update-pinned-actions.sh`: `usage()` function now exits with code 1 instead of 0 on invalid usage
- `.claude/settings.json`: replace broad `Bash(git *)` allow entry with 21 explicit subcommand entries (`git status`, `git diff`, `git add`, `git commit`, `git log`, `git fetch`, `git pull`, `git branch`, `git stash`, `git show`, `git rev-parse`, `git merge-base`, `git worktree`, `git tag`, `git describe`, `git blame`, `git ls-files`, `git remote`, `git config`, `git rebase`, `git apply`) to eliminate allow/deny ordering ambiguity reported in Claude Code bug #26276
- `.claude/settings.json`: replace broad `Bash(gh pr *)` allow entry with four read-only subcommands (`gh pr view*`, `gh pr list*`, `gh pr checks*`, `gh pr diff*`) to prevent unintended `gh pr merge`, `gh pr close`, and `gh pr create` operations
- `.claude/settings.json`: remove unbounded `Write(*.json)` and `Edit(*.json)` allow entries; all legitimate JSON write targets are already covered by the path-scoped `.github/**`, `docs/**`, and `.claude/**` patterns
- `.claude/settings.json`: add wildcard-middle deny patterns for mutating HTTP methods (`Bash(gh api * -X POST*)`, `Bash(gh api * --method POST*)`, `Bash(gh api * -X PUT*)`, `Bash(gh api * --method PUT*)`, `Bash(gh api * -X DELETE*)`, `Bash(gh api * --method DELETE*)`, `Bash(gh api * -X PATCH*)`, `Bash(gh api * --method PATCH*)`) to block flag orderings where the method flag appears after the endpoint URL; existing prefix-only patterns (e.g. `Bash(gh api -X POST*)`) are retained to cover the flag-first ordering
- `.claude/settings.json`: add `Bash(rm -fr*)` deny entry to block the `-fr` flag-order variant not covered by the existing `Bash(rm -r*)` and `Bash(rm -f*)` entries
- `.claude/settings.json`: `Write(.claude/**)` and `Edit(.claude/**)` intentionally kept broad to allow transient writes to gitignore'd subdirectories (worktree state, tool caches); these paths are excluded from the repo via `.gitignore`
- `.gitignore`: replace 8 enumerated `.claude/<subdir>/` exclusion entries with a catch-all `.claude/*` plus negations for `!.claude/CLAUDE.md` and `!.claude/settings.json`; new repos and new transient subdirs are excluded automatically without requiring manual `.gitignore` updates
- `.github/workflows/pr-validation.yml`, `USAGE_EXAMPLES.md`, `docs/audits/2026-05-01-security-audit.md`: replace em-dash characters with colons and commas in error messages, list bullets, and documentation prose; resolves `no-em-dash` pre-commit hook violations (CLAUDE-007)
- Rename org identity from `williaby` to `ByronWilliamsCPA` across 19 community health, documentation, and example files: `CODEOWNERS`, `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, `FUNDING.yml`, `GOVERNANCE.md`, `ISSUE_TEMPLATE/config.yml`, `QLTY_INTEGRATION.md`, `README.md`, `REUSE.toml`, `SUPPORT.md`, `pull_request_template.md`, `profile/README.md`, and seven workflow documentation and example files; updates all GitHub URLs, workflow `uses:` references, and contact pointers; extends copyright year to `2025-2026`

### Security

- `.pre-commit-config.yaml`: upgrade TruffleHog from `repo: local` with a pinned system binary to `repo: https://github.com/trufflesecurity/trufflehog` at SHA `05cccb53bc9e13bc6d17997db5a6bcc3df44bf2f` (v3.92.3); upstream repo is the recommended distribution channel; adds `scorecard.yml` warning about the `SCORECARD_TOKEN` scope requirement
- Remediate SonarCloud S7630 script injection in 9 workflow files: move all `${{ inputs.* }}` references used in `run:` shell bodies to `env:` blocks; affects `python-ci.yml`, `python-compatibility.yml`, `python-docs.yml`, `python-mutation.yml`, `python-publish-pypi.yml`, `python-release.yml`, `python-sbom.yml`, `python-sonarcloud.yml`, `python-performance-regression.yml`
- Remediate SonarCloud S8233/S8264 permission over-grant in 14 workflow files: move workflow-level `permissions:` blocks to per-job scope to enforce least-privilege; `id-token: write` and `pages: write` grants preserved at per-job level where required
- Remediate SonarCloud S8541/S8544 in 7 workflow files: add `--frozen --no-build` to `uv sync` and `uv pip install` commands; add `--only-binary :all:` to `pip install cyclonedx-bom==7.3.0` (`python-sbom.yml`, `python-release.yml`) and `pip install twine==6.2.0` (`python-publish-pypi.yml`)
- Remediate SonarCloud S6506 TLS enforcement: add `--proto '=https' --tlsv1.2` to all `curl` invocations in `sync_org_files.sh` (including the per-file download loop at line 67 that was missed in the initial remediation) and `self-test.yml`
- Remediate SonarCloud S6573 glob safety: replace `sha256sum *` with `sha256sum ./*` in `self-test.yml`
- Fix CodeQL code injection in `python-container-security.yml`: move `${{ steps.check-dockerfile.outputs.exists }}` from `run:` shell body to `env:` block as `EXISTS`
- Fix shell injection via unquoted `$EXTRAS` expansion in `python-sonarcloud.yml` and `python-performance-regression.yml`: replace string-splitting pattern with bash array (`EXTRA_ARGS=()` / `"${EXTRA_ARGS[@]}"`) so each extra name is a distinct quoted argument
- Pin loose version constraints: `mutmut>=2.0.0` to `mutmut==2.5.1` in `python-mutation.yml`; `reuse>=5.0` to `reuse==5.0.2` in `python-reuse.yml`
- `python-publish-pypi.yml`, `python-reuse.yml`: remediate SonarCloud S8541 and S8544 in tool install steps; `uv run --with pip-audit==2.10.0` and `uv run --with bandit[toml]==1.9.4` flagged S8541 for executing arbitrary build scripts from source distributions; `pip install --only-binary :all: reuse==5.0.2` flagged S8544 for unlocked transitive dependencies; replace with `uv pip install --no-build 'pkg==version'` plus direct invocation; add conditional `astral-sh/setup-uv` step to `python-reuse.yml` so `uv` is available when `generate-spdx: true`
- Fix script injection vulnerability in `python-codecov.yml`: move `inputs.coverage-files` to env var before shell use (SonarCloud S7630)
- Pin `slsa-framework/slsa-github-generator` to full commit SHA in `python-slsa.yml` (SonarCloud S7637)

## [2026-04-13]

### Fixed

- LLM governance: replace `fromJSON` with direct numeric comparison for `critical_tags`
- LLM governance: only block PRs on `#CRITICAL` tags; demote `#ASSUME` to warning
- Security: add `pull-requests: read` permission to detect-changes job
- CI: move `fromJSON` to outer level in matrix strategy ternary

## [2026-04-10]

### Changed

- Update action pins ahead of Node.js 20 deprecation deadlines

### Fixed

- SBOM: use exact filename for `upload-artifact` path
- SBOM: resolve `upload-artifact` path via `github.workspace` context
- SBOM: downgrade `upload-artifact` to v4.5.0 to fix glob resolver
- SBOM: anchor SBOM output path to `GITHUB_WORKSPACE`
- SBOM: repair silent generation failure in `python-sbom` workflow

## [2026-04-05]

### Added

- Trivy `.trivyignore` file support in container security workflow
- Harbor registry setup documentation

## [2025-11-23]

### Added

- Initial reusable workflow library for Python projects
- Workflows: CI, PR validation, coverage upload, SLSA provenance, SBOM, security analysis, SonarCloud, ScoreCard, release, publish to PyPI
- Shared community health files: SECURITY.md, CONTRIBUTING.md, SUPPORT.md, issue templates

[Unreleased]: https://github.com/ByronWilliamsCPA/.github/compare/2026-04-13...HEAD
[2026-04-13]: https://github.com/ByronWilliamsCPA/.github/compare/2026-04-10...2026-04-13
[2026-04-10]: https://github.com/ByronWilliamsCPA/.github/compare/2026-04-05...2026-04-10
[2026-04-05]: https://github.com/ByronWilliamsCPA/.github/compare/2025-11-23...2026-04-05
[2025-11-23]: https://github.com/ByronWilliamsCPA/.github/releases/tag/2025-11-23
