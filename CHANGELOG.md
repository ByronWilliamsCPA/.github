# Changelog

All notable changes to this project's shared workflow templates are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

This project uses date-based version headers (e.g. `[2025-01-07]`) rather than
semver because it is a shared workflow library with continuous deployment; there
are no numbered releases.

## [Unreleased]

### Added

- `python-sbom.yml`: OSV-Scanner runs alongside Trivy and Grype as a third
  SBOM-ingest sibling job (`scan-runtime-osv`) for fast keyless CVE coverage
  per issue #152 follow-up. Adds new optional input `run-osv` (default `true`)
  that lets callers opt out. The job ingests the same `sbom-runtime.json`
  artifact that Trivy and Grype use, so no second resolver pass occurs.
  SARIF is uploaded under category `osv-sbom-runtime-deps`, surfacing
  alongside Trivy and Grype categories on the Security > Code scanning tab.
  Reuses the OSV-Scanner action SHA already pinned in
  `python-security-analysis.yml` (no new third-party surface). Gating mirrors
  Trivy: when `fail-on-vulnerabilities: true` (the default), an OSV finding
  fails the workflow. Caller surface is backwards-compatible; one new check
  entry appears in PR Checks UI for repos that keep the default.
- `sbom-nightly.yml`: org-level nightly workflow that calls `python-sbom.yml`
  on a daily 02:17 UTC schedule plus `workflow_dispatch`. Skips cleanly in
  `.github` (no `pyproject.toml`); serves as the reference pattern for
  downstream repos that want nightly CVE database coverage between PR builds.
  Documents the schedule-trigger snippet downstream repos can paste into
  their own `python-sbom.yml` caller workflows so vulnerabilities disclosed
  after the last PR build are caught within 24 hours.

- `python-sbom.yml`: Grype scanning runs alongside Trivy as a non-gating sibling
  job (`scan-runtime-grype`) for a 30-day parity window per issue #152. Adds new
  optional input `grype-config-path` (default `.grype.yaml`) and a
  `parity-summary` job that downloads both scanners' SARIF artifacts and writes
  a CVE-level set-diff (findings detected by both, by Trivy only, by Grype only)
  to the run summary. Trivy remains the gating scanner during parallel-run; the
  Grype job is non-gating via `continue-on-error: true` at the job level so
  genuine action failures still surface as a failed step in the logs while the
  workflow caller never blocks on Grype. The caller-supplied `grype-config-path`
  is validated against path-traversal (`..`) and absolute-path patterns before
  it reaches `actions/checkout` sparse-checkout or `anchore/scan-action`.
  Scanner SARIF is also uploaded as a workflow artifact (`trivy-sarif`,
  `grype-sarif`, 7-day retention) so the parity comparison can run on the
  actual finding sets rather than on job results alone. Caller surface is
  backwards-compatible; two new check entries appear in PR Checks UI. The
  `trivyignore-path` input is marked deprecation-pending for removal at the
  Trivy cutover. Motivation: Trivy release infrastructure compromise (March
  2026) makes the SBOM scanner itself a supply-chain risk; Grype (Anchore) is
  unaffected.

- `scripts/fleet-audit-sha-pins.sh`: new `STRICT_AUDIT=1` environment toggle.
  When set, the script exits with status 2 if any repo emitted a `repo,error`
  row or if any org's repo count saturated `REPO_LIMIT`. CI gates that need
  fail-closed semantics opt in via `STRICT_AUDIT=1`; the default flow remains
  report-only (exit 0) so existing consumers are unaffected. Companion
  change: `REPO_LIMIT` now reads from environment with a default of 1000
  (`REPO_LIMIT="${REPO_LIMIT:-1000}"`), letting tests exercise the
  saturation WARN with a small stub-friendly value and giving operators an
  escape hatch for fleets that grow beyond the default.
- `scripts/fleet-audit-sha-pins.sh`: `STRICT_AUDIT` now accepts the
  case-insensitive truthy spellings `1`, `true`, and `yes`; previously only
  the literal `"1"` was honoured and `STRICT_AUDIT=true` silently degraded
  to report-only.

### Breaking Changes

- `python-security-analysis.yml`: the `safety` SCA scanner has been
  removed from the reusable workflow and its `workflow-templates/`
  mirror. Three downstream-visible surfaces change:

  1. **Input removed.** The `run-safety` boolean input is gone.
     Callers still passing `run-safety:` in their `with:` block will
     fail GitHub Actions workflow-call input validation and the run
     will not start.
  2. **Required-check name change.** The `python-security` job display
     name changed from `Python Security Scan` to `Python SAST (Bandit)`.
     Consumer repos with branch protection rules or required-check
     configurations referencing the old name will see merges silently
     blocked until those rules are updated.
  3. **Conditional narrowed.** The `python-security` job's `if:`
     condition changed from `run-bandit || run-safety` to `run-bandit`
     alone. Callers that previously set `run-bandit: false,
     run-safety: true` to scope scanning to dependency CVEs only now
     receive no Python security job at all.

  Migration:

  1. Remove `run-safety:` from any `with:` block in caller workflows.
  2. Rename references to `Python Security Scan` in branch protection
     rules and required-check configurations to `Python SAST (Bandit)`.
  3. If you depended on the `run-bandit: false, run-safety: true`
     configuration, drop the `run-safety: true` line; dependency
     vulnerability scanning is now performed exclusively by OSV-Scanner
     and the Dependency-Review action.

  Rationale: `safety` is the only Python dep CVE scanner in the fleet
  whose data sources are a strict subset of OSV-Scanner's. Removal
  eliminates the cascading regressions traced in PRs #136/#137/#138
  and the editable-install blocker from #138's merged form.

- `python-precommit.yml`: the `fail-fast` input has been renamed to `show-diff-on-failure` to accurately reflect what it controls. Callers passing `fail-fast:` in their `with:` block must update to `show-diff-on-failure:`. Default value (`true`) and type (`boolean`) are unchanged.

  Migration: update your caller workflow's `with:` block as follows.

  Before:
  ```yaml
  with:
    python-version: '3.12'
    fail-fast: true
  ```

  After:
  ```yaml
  with:
    python-version: '3.12'
    show-diff-on-failure: true
  ```

### Added

- All 11 reusable Python workflows: `no-build` boolean input (default `true`) controls whether `--no-build` is passed to `uv sync`/`uv run` commands; allows repos with a build backend (hatchling, setuptools) to opt out of the flag that prevented local package installation; routed through a job-level `NO_BUILD_FLAG` env var so callers need only set `no-build: false` in their `with:` block
- `SECURITY.md`: Security Surface Areas section documenting the threat model for this workflow library
- `python-precommit.yml`: new reusable workflow that runs `pre-commit run --all-files` in the project virtualenv via `uv run`; inputs `config-path`, `python-version`, `show-diff-on-failure`, `no-build`; all inputs via env vars; SHA-pinned actions
- `python-standard-stack.yml`: new composite reusable workflow chaining `python-ci.yml`, `python-security-analysis.yml`, and `python-sbom.yml` via `needs:`; recommended quickstart for new repos; exposes `python-version`, `source-directory`, `coverage-threshold`, `fail-on-high`; optional `SONAR_TOKEN`/`CODECOV_TOKEN` passthroughs
- `python-supplemental-checks.yml`: `enable-commit-lint` input (default false) that validates PR titles against Conventional Commits format via SHA-pinned `amannn/action-semantic-pull-request`; commit-lint status added to supplemental summary
- `python-scorecard.yml`: `min-score` input (type: number, default 0 = gate disabled) and `Evaluate Scorecard Scores` step that parses SARIF output and fails CI if any of Branch-Protection, Code-Review, Dangerous-Workflow, Token-Permissions, or Pinned-Dependencies scores below the threshold
- `workflow-templates/python-ci.yml`, `python-security-analysis.yml`, `python-sonarcloud.yml`, `python-cifuzzy.yml`, `python-compatibility.yml`, `python-container-security.yml`, `python-docs.yml`, `python-fips-compatibility.yml`, `python-reuse.yml`: unfiltered `merge_group:` trigger so each gate produces a check on the queue's speculative merge commit. Without it, repos that enable `merge_queue` in their branch ruleset cannot satisfy required-status-check policies for PRs that list these workflows as required. The trigger is purely additive and inert until a consumer repo enables `merge_queue`. `python-pr-validation.yml` is intentionally excluded because the reusable workflow it calls is deprecated. See standards-manifest `CI-040`; refs #154.
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
- `--pin-tags` mode in `scripts/update-pinned-actions.sh` to convert `@vN` tag refs to 40-character commit SHA pins. Closes #153.
- `scripts/fleet-audit-sha-pins.sh` for read-only enumeration of third-party tag/branch refs across both orgs.

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
- `python-ci.yml`: add `Validate source layout` precondition step that fails fast with an actionable `::error::` block when `source-directory` or `test-directory` does not exist, replacing the previous opaque `Failed to format src: No such file or directory` failure from ruff; step uses explicit `shell: bash` and reads inputs via `env:`; behavior change for misuse cases (callers without `src/`/`tests/` now fail one step earlier with a clearer message), no breaking change for correctly configured callers
- `docs/workflows/python-ci.md`: new docs page documenting the required `src/` layout, when to use vs not use the workflow, flat-layout support via `source-directory: '.'` override, minimal usage example, and selected inputs

### Fixed

- `python-docs.yml`: gate the `deploy` job on the `build` job's detected state to prevent `actions/download-artifact` from failing with "artifact not found" when a caller passes `deploy-to-pages: true` from a repo without `pyproject.toml`. The build job now exposes `steps.detect.outputs.state` as a job-level output, and `deploy`'s `if:` clause requires `needs.build.outputs.state != 'skip'`. Without this guard, build succeeded in skip mode (only the skip-notice step ran; the upload-artifact step was already conditionally skipped) and `needs: build` falsely cleared deploy to run against a missing artifact (PR #171, addresses Copilot inline review)
- `python-mutation.yml`: apply the Wave 1C strengthened detect-state pattern (per #166, #170): split the prior single `Install dependencies` step into two `if:`-guarded single-line `run:` steps (`uv-locked` carries literal `--frozen`; `uv-no-lock` omits it), reject Poetry repos with an actionable error, and skip cleanly when no `pyproject.toml` is present. The skip path now emits deterministic `score=0`, `passed=true`, and `skipped=true` outputs (via a coalescing job-output expression) so downstream callers no longer receive empty strings that silently fail `passed == 'true'` conditionals; `skipped` is exposed as a new `workflow_call` output so sophisticated callers can distinguish "skipped" from "tested and passed". The nested `uv run mutmut results --json` subprocess inside the analyze step's Python heredoc now honors `--frozen` and `$NO_BUILD_FLAG`, restoring the lockfile/no-build guarantee that the other `uv run` invocations carry (PR #172)
- `python-ci.yml`: replace `DEAD_CODE_COUNT=$(echo "$VULTURE_OUTPUT" | grep -c ":" || echo "0")` with `... || true` on line 228; `grep -c PATTERN` prints `0` to stdout on no-match and exits 1, so the previous `|| echo "0"` cascade appended a second `0` to the count on the edge case where `vulture` (running with `2>&1`) emits non-finding output containing no `:` (Python traceback, env warning, UnicodeError, etc.), producing a `"0\n0"` value that rendered as a broken `**Found 0\n0 potential dead code issue(s)**` markdown line in the step summary; the common path (vulture finds dead code with `file:line:` patterns) was unaffected and remains unchanged; same family of bash subtlety as the #126 backtick bug fixed in #127; fixes #132
- `python-ci.yml`: escape backticks around `` `.vulture_whitelist.py` `` in the Vulture step's `GITHUB_STEP_SUMMARY` write (line 240); the unescaped backticks inside a double-quoted `echo` triggered bash command substitution, which tried to execute `.vulture_whitelist.py` as a command, exited 127, and failed the step under `set -e` even when callers passed `fail-on-dead-code: false`; the failure manifested as `command not found` after the dead-code check itself had already succeeded, blocking CI Gate green in every downstream caller; fixes #126
- `python-reuse.yml`: replace `uv pip install --no-build 'reuse==5.0.2'` in the SPDX generation step with a second invocation of `fsfe/reuse-action` (pinned to v6.0.0) passing `args: spdx -o reuse-spdx.spdx`; PyPI publishes only one wheel per `reuse` release (e.g., 5.0.2 cp313-only, 6.2.0 cp310-only), so the runner's `uv venv` against system CPython 3.12 found no matching wheel and `--no-build` (the S8541/S8544 mitigation from #110) forbade the sdist fallback, causing the job to fail after a successful REUSE lint; the Docker image carries `reuse` for the correct Python ABI, sidestepping the wheel mismatch without weakening the host-side `--no-build` posture; also gate `Upload SPDX artifact` on the SPDX step outcome (`steps.spdx.outcome == 'success'`), move `${{ steps.*.outcome }}` interpolations into env vars in the Summary step (workflow-injection mitigation), distinguish `success`, upload failure, `skipped`, and `failure` in the SPDX status line of the job summary, and add an `#ASSUME` comment documenting that SPDX still runs against a non-compliant tree when callers pass `fail-on-missing: false`; fixes #124
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
- `scripts/fleet-audit-sha-pins.sh`: bump `gh repo list --limit` from 200 to 1000 and warn when the result saturates the limit, so a fleet that grows beyond the bound surfaces an audible WARN instead of silently truncating

### Fixed

- `scripts/fleet-audit-sha-pins.sh`: distinguish legitimate HTTP 404 (no workflows directory) from real API failures (rate limit, 5xx, auth loss); real failures now emit a `repo,error` sentinel row and a stderr WARN line instead of silently appearing as `repo,0`. The 404 discriminator now requires the exact `(HTTP 404)` parenthesized form so an upstream 5xx response containing the substring "Not Found" cannot be misclassified as a missing resource. Replaces the regex-based `SKIP_OWNERS` check with a literal `case` match so operator-supplied values containing regex metacharacters (e.g., `.*`) cannot silently classify every owner as skipped. Adds a stderr WARN when a per-file 404 occurs mid-iteration (the directory listing succeeded but the specific file fetch returned 404, indicating a race or scope mismatch). Replaces the silent `|| true` masking on the base64 decode with explicit rc handling that propagates decode failures to the `repo,error` sentinel. Addresses the silent-failure and regex-injection findings from the PR #175 follow-up review.
- `scripts/update-pinned-actions.sh`: `extract_tag_pins` and `extract_branch_pins` now accept refs that carry an inline `# comment` (e.g., `actions/checkout@v4  # stable`); the converter previously required the ref to be the last non-whitespace content on the line, leaving inline-annotated refs as lingering audit violations. The sed substitution in `--pin-tags --apply` now spans to end-of-line so any pre-existing inline comment is replaced cleanly by the new `# <tag>` comment. Escapes sed-replacement metacharacters (`\`, `&`, `|`) in the resolved tag name AND sed-pattern metacharacters in `current_tag` and `full_action` before splicing into the substitution; a semver `.` in `current_tag` no longer matches arbitrary characters and tags containing the sed delimiter `|` no longer terminate the pattern field. Replaces the regex-based `--owner-allowlist` filter in both extractors with an awk literal-string lookup, eliminating the regex-injection vector where `--owner-allowlist '.*'` would silently classify every action as first-party. Replaces the `{ pipeline; } || true` wrappers in both extractors with explicit grep rc handling so a real failure (rc>=2: unreadable directory, permission denied) surfaces as a stderr WARN and a non-zero return instead of a silent empty result. Replaces the two-call `resolve_tag_sha` pattern with a single composite-jq fetch, removing the race window where a force-push or rate-limit hit between two fetches of the same ref could return disagreeing values. Makes the EXIT trap BSD-compatible by using `${VAR:+"$VAR"}` so `rm -f` never receives an empty-string argument on macOS. Hoists the `CHANGE_LOG` temp file and its cleanup trap to script scope so `pin_tags_main` no longer relies on a function-local `RETURN` trap; both extractor pipelines tolerate zero matches under `set -euo pipefail` via the new rc-aware path.
- `tests/update-pinned-actions.bats`, `tests/fleet-audit-sha-pins.bats`: add eight new test cases covering the hardening above. The five from the original PR #175 follow-up commit (inline-comment conversion, custom `--owner-allowlist`, two-step annotated-tag dereferencing, audit emits `repo,error` on non-404 failure, audit treats 404 on the workflows directory as a legitimate zero) are joined by three regression-vector tests: sed-escape of `&` and `|` characters in tag-name comments, `--skip-owners` with regex metacharacters still counts violations, and mixed-success inner-loop (one workflow file fetches OK, a second fails, repo row flips to `error` not a partial numeric count).
- `scripts/update-pinned-actions.sh`: `resolve_tag_sha` now validates that the `gh api` composite jq response contains non-empty, non-`"null"` values for `.object.type` and `.object.sha`. The previous code accepted the literal string `"null"` (emitted by `jq -r` for missing fields) as a successful resolution, which produced patterns like `actions/checkout@null` that the caller wrote into the workflow file. The same guard now also fires after the second annotated-tag dereferencing call. Action refs that fail validation are marked SKIPPED rather than written with a malformed SHA.
- `tests/fleet-audit-sha-pins.bats`, `tests/update-pinned-actions.bats`: add nine more regression-vector tests guarding the Suggested-tier fixes. fleet-audit gains: REPO_LIMIT saturation WARN with env-overridable REPO_LIMIT, STRICT_AUDIT=1 fail-closed on saturation, STRICT_AUDIT=1 fail-closed on per-repo error, STRICT_AUDIT=1 clean-run regression guard, SKIP_OWNERS edge cases (single value, empty, double internal commas). update-pinned-actions gains: extract_branch_pins reports comment-annotated branch refs, --pin-tags --apply succeeds with only-first-party fixtures, --pin-tags --apply skips when annotated-tag dereferencing returns missing `.object.sha`.
- `scripts/fleet-audit-sha-pins.sh`: workflows-listing failure path now sets `audit_incomplete=true` before continuing, matching the per-file-fetch error path. The previous code emitted a `repo,error` sentinel but left the flag unset, so `STRICT_AUDIT=1` could exit 0 even when error rows were present. Verified by the new `STRICT_AUDIT=1 exits non-zero on workflows-listing failure` regression test. (Critical from the PR #177 self-review.)
- `.github/workflows/shell-tests.yml`: bats runner now discovers all `tests/*.bats` files via `find ... -print0 | xargs -0`. Previously it named only `tests/update-pinned-actions.bats`, so the 13 cases in `tests/fleet-audit-sha-pins.bats` (including the STRICT_AUDIT and REPO_LIMIT regression cases added in PR #176 and PR #177) never ran in CI. (Critical from the PR #177 self-review.)
- `scripts/fleet-audit-sha-pins.sh`: `gh repo list` invocation now captures stdout to a temp file rather than reading through process substitution, so the command's exit code surfaces. An auth-loss or rate-limit hit during enumeration now flags the audit as incomplete and emits a stderr WARN; previously the failure was discarded and the org silently contributed zero rows.
- `scripts/fleet-audit-sha-pins.sh`: validate `REPO_LIMIT` as a positive integer up front and exit 1 with a clear error message when it is empty, zero, negative, or non-numeric. Previously a bad value would crash mid-loop inside `[[ ... -eq $REPO_LIMIT ]]` under `set -euo pipefail`.
- `scripts/update-pinned-actions.sh`: `resolve_tag_sha` null guards now emit a stderr WARN before returning empty, so operators can distinguish a malformed GitHub API response from a missing tag. The action is still marked SKIPPED; only the diagnostic surface changes.
- `scripts/fleet-audit-sha-pins.sh`: strip trailing CR from each line before regex matching in the violation counter, so workflow files checked out on Windows or proxied through CRLF-normalizing intermediaries no longer leak `\r` into `BASH_REMATCH[4]` and inflate violation counts.

### Security

- Phase 1 security remediation across four reusable workflows (PR #117):
  - `python-qlty-coverage.yml`: move `${{ github.event.repository.name }}` and `${{ github.repository_owner }}` into the step `env:` block in the Coverage Upload Summary step; the values are now referenced as `$REPO_NAME` and `$REPO_OWNER` instead of being interpolated as raw text inside the shell `run:` body
  - `python-fips-compatibility.yml`: add allowlist regex validation for the `script-path` input before any file or execution step; rejects absolute paths, `..` traversal, and any characters outside `[a-zA-Z0-9_./-]`; requires a `.py` extension; additionally resolve the path via `realpath -e` when the file exists and confirm the canonical target stays inside `$GITHUB_WORKSPACE`, blocking symlink-escape attempts that bypass the regex
  - `python-performance-regression.yml`: same allowlist regex applied to the `benchmark-script` input in the Validate Benchmark Script step, plus the same `realpath -e` workspace-containment check
  - `python-security-analysis.yml`: remove `|| true` from the Bandit Static Analysis step so real findings fail the job; collapse the duplicate fail-only invocation into a single call that writes the JSON report and propagates the exit code; apply the same fix to the Safety Vulnerability Scan step (remove `|| true` from the JSON-producing call and drop the redundant fail-only invocation); false positives should be handled via `.bandit` config or inline `# nosec` for Bandit, and via Safety's ignore mechanism or a policy file for Safety, not exit-code suppression
- `python-security-analysis.yml`: `security-gate` job `harden-runner` `egress-policy` remains `audit`; an attempt in #121 to set it to `block` was reverted in #136 because `step-security/harden-runner@v2.19.2` with `egress-policy: block` and no `allowed-endpoints` configuration fails at workflow load time, producing `startup_failure` in every consumer repo's Security Analysis run before any job is materialized (observed in `ByronWilliamsCPA/fragrance-rater` PR #22 and `ByronWilliamsCPA/llc-manager` main); the `security-gate` job has no outbound network calls so `block` remains the correct least-privilege target, but the proper fix is `egress-policy: block` paired with an explicit `allowed-endpoints` allowlist (or `allowed-endpoints: ""`), not `block` alone; the other jobs (`codeql`, `dependency-review`, `python-security`, `osv-scanner`) retain `egress-policy: audit` because they perform legitimate network operations (dependency fetch, CodeQL upload, OSV database queries); relates to #116
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
- Swept consumer repos to pin third-party GitHub Actions by commit SHA. Defends against retroactive tag-pointer manipulation (CVE-2025-30066 class). Per-repo PRs filed; CI-060 promoted to `severity: important` in the standards manifest after sweep completes.

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
