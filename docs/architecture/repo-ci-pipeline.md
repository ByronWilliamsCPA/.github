
# This Repo's Own CI/CD Pipeline

Status: Reference
Date: 2026-07-14

## Scope: self-CI, not the reusable workflow catalog

`ByronWilliamsCPA/.github` publishes reusable `workflow_call` workflows (the `python-*.yml`
files) that other repos consume via `uses:` and `with:`. Those are documented individually
under `docs/workflows/*.md` using a "how a caller uses this" template: inputs, secrets,
outputs, and a consumer integration example.

The 16 workflows covered here are different: they are this repo's own internal CI/CD,
triggered by `push`, `pull_request`, `schedule`, or `merge_group` against this repo's own
commits and PRs. Nobody `uses:` them externally. A few (`qlty.yml`, `codeql.yml`,
`dependency-provenance-weekly.yml`, `sbom-nightly.yml`, `snyk-weekly.yml`,
`security-analysis.yml`, `scorecard.yml`) are thin callers into this repo's own reusable
workflows, but the caller file itself only exists to exercise and validate that reusable
against this repo's own content: it is self-test, not distribution. This document explains
what this repo's own build, security, and release pipeline does and why, for a maintainer
or contributor reading the repo, not for a downstream integrator.

## Categories

- [PR and merge-queue gating](#pr-and-merge-queue-gating): required checks that block a merge.
- [Self-testing and quality](#self-testing-and-quality): validates this repo's own
  workflows, scripts, and code quality.
- [Scheduled security and supply-chain scanning](#scheduled-security-and-supply-chain-scanning):
  vulnerability and provenance scans, mostly schedule-driven.
- [Release automation](#release-automation): cuts the semver tag consumers pin to.

## PR and merge-queue gating

Checks that gate `pull_request` (and, where noted, `merge_group`) events. These are the
checks a contributor sees fail directly on their own PR.

### pr-validation.yml

- Trigger: `merge_group:` and `pull_request: types: [opened, synchronize, reopened, edited]`,
  `branches: [main, master]`.
- Purpose: enforces Conventional Commits PR titles and a non-empty PR body.
- Where to look when red: the `PR Validation Gate` job writes a summary table to
  `GITHUB_STEP_SUMMARY`; read that first. `title-check` fails on a title that does not
  match `^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\([^()]+\))?!?: .+`;
  `body-check` fails on an empty or whitespace-only body. Both jobs are skipped (treated as
  pass) on `merge_group` refs, since the PR payload is unavailable there.

### pre-commit.yml

- Trigger: `push: branches: [main]` and `pull_request:` (no path filter, so it runs on
  every change including docs-only PRs).
- Purpose: runs the full `.pre-commit-config.yaml` hook suite (yamllint, markdownlint,
  file checks, detect-secrets, TruffleHog, no-em-dash) in CI, not only for contributors who
  ran `pre-commit install` locally.
- Where to look when red: the `Run pre-commit hooks` job's `Run pre-commit` step runs with
  `--show-diff-on-failure`, so the failing hook and the diff it wants are in that step's
  log. If the run fails earlier at `Install pre-commit` or `Create virtual environment`,
  check that `uv venv` ran before `uv pip install` (pre-commit requires an existing `.venv`,
  see issue #106).

### dependency-review.yml

- Trigger: `pull_request: branches: [main]`.
- Purpose: blocks a PR that introduces a dependency with a high-or-above severity advisory
  or a disallowed license.
- Where to look when red: the `Dependency Review` step. `fail-on-severity: high` is the
  severity gate; `allow-licenses` lists the approved licenses (MIT, Apache-2.0,
  BSD-2-Clause, BSD-3-Clause, ISC, CC0-1.0, CC-BY-4.0). A red run names the offending
  package and its advisory or license directly in the action's summary.

### reuse.yml

- Trigger: `merge_group:`; `pull_request: paths: ["**/*", "REUSE.toml", "LICENSES/**",
  ".github/workflows/reuse.yml"]`; `push: branches: [main, master, develop]`.
- Purpose: validates REUSE 3.0 SPDX license-header compliance across the repo.
- Where to look when red: the `Check REUSE Compliance` step (`fsfe/reuse-action`) names the
  file missing an SPDX header or copyright tag. The sibling `validate-licenses` job checks
  that `LICENSES/MIT.txt` and `REUSE.toml` exist at all; a failure there means one of those
  two files was deleted or moved.

### claude-baseline-review-pr.yml

- Trigger: `pull_request: types: [opened, synchronize, reopened, ready_for_review, edited]`,
  `branches: [main]`.
- Purpose: thin caller that runs the reusable Tier 0 Claude baseline reviewer
  (`claude-baseline-review.yml`) against this repo's own PRs, supplying this repo's
  description, sensitive paths, and escalation guidance.
- Where to look when red: check the `review` job's `permissions:` block first
  (`contents: read`, `pull-requests: write`, `issues: write`, `id-token: write`); the file's
  own comment flags that omitting any one of these fails the reusable at startup because a
  called workflow's token is bounded by the caller job's grant. If permissions are correct,
  the failure is inside the reusable's own run (prompt or model error).

### sonarcloud.yml

- Trigger: `push: branches: [main]`; `pull_request: types: [opened, synchronize,
  reopened]`; `workflow_dispatch:`.
- Purpose: SonarCloud static analysis of shell scripts, YAML, and configuration (no Python
  in this repo, so SonarCloud auto-detects the rest).
- Where to look when red: the `SonarCloud Scan` step runs only when
  `github.event.pull_request.head.repo.full_name == github.repository` is true (or the
  event isn't a `pull_request`), so a fork PR shows the job skipped, not failed, that's
  expected since `SONAR_TOKEN` isn't exposed to fork PRs. On a same-repo run, check
  `SONAR_TOKEN` and `GITHUB_TOKEN` are set and read the SonarCloud dashboard for the actual
  quality-gate finding.

## Self-testing and quality

Workflows that validate this repo's own workflow files, shell scripts, and code quality,
rather than PR content in the conventional-commits/license sense above.

### self-test.yml

- Trigger: `push: branches: [main]` and `pull_request:`, both path-filtered to
  `.github/workflows/**`, `workflow-templates/**`, `**/*.sh`, `**/*.bash`, and
  `.github/workflows/self-test.yml`.
- Purpose: lints this repo's own workflow YAML and shell scripts so regressions in the
  reusable workflows are caught before they propagate to every consumer; also enforces the
  documented Python version policy and self-tests the `python-dependency-provenance.yml`
  reusable end to end.
- Where to look when red: `Lint workflow files (actionlint)` names the exact file and line
  (it also runs shellcheck on every embedded `run:` block, filtered to `--severity=warning`
  via `SHELLCHECK_OPTS`); `Lint shell scripts (shellcheck)` covers standalone `.sh`/`.bash`
  files; `Enforce Python version policy` runs `scripts/check-python-versions.sh`, run that
  script locally against `docs/python-versions.md` to reproduce.

### shell-tests.yml

- Trigger: `push:` and `pull_request:`, both path-filtered to `scripts/**`, `tests/**`, and
  `.github/workflows/shell-tests.yml`.
- Purpose: runs the Bats suites covering six of the nine `scripts/*.sh` scripts (see repo
  `.claude/CLAUDE.md` for which four are not yet covered) plus the Python tests under
  `tests/python/`.
- Where to look when red: `Bats Tests` discovers every `tests/*.bats` file via `find`
  (not a single named file, so new suites are picked up automatically); the failing test
  name is in that job's log. `Python Tests` runs `pytest tests/python/ -v` via `uvx` pinned
  to `pytest==9.0.3`.

### qlty.yml

- Trigger: `pull_request: branches: [main]`; `schedule: cron '0 7 * * 1'` (Monday 07:00
  UTC); `workflow_dispatch:`.
- Purpose: two jobs from one file. `qlty-gate` runs on `pull_request` in diff mode against
  `origin/<base_ref>` and blocks merges on medium-or-above severity issues in the diff; the
  required check is named `qlty-gate / Qlty Gate` per the org's docs-tier ruleset.
  `qlty-health` runs on `schedule`/`workflow_dispatch` as a full-codebase, informational-only
  scan (`no-fail: true`, `fail-level: high`) until existing debt is resolved.
- Where to look when red: for a PR failure, check the `qlty-gate / Qlty Gate` job and the
  diff against `origin/${{ github.base_ref }}`; `qlty-health` cannot go red today because
  `no-fail: true` suppresses failure, so treat its findings as advisory only.

## Scheduled security and supply-chain scanning

Vulnerability, SAST, and provenance scans. Most run primarily on `schedule`, deliberately
off the `pull_request` path where noted (metering or noise reasons), with a few exceptions
(`codeql.yml`, `security-analysis.yml`) that also gate `push`/`pull_request` directly.

### codeql.yml

- Trigger: `push: branches: [main, master]`; `pull_request: branches: [main, master]`;
  `schedule: cron '0 7 * * 1'` (Monday 07:00 UTC); `workflow_dispatch:`.
- Purpose: CodeQL SAST on the `actions` language (this repo's workflow YAML), using the
  `security-extended,security-and-quality` query suites.
- Where to look when red: `CodeQL Analyze` job, `Initialize CodeQL` or `Perform CodeQL
  Analysis` steps. If the whole job fails oddly (SARIF upload rejected), check that
  GitHub's Code Scanning "default setup" is still disabled in Settings > Code security >
  Code scanning: default setup and this repo's advanced configuration cannot both upload
  SARIF, per the file's own header comment.

### security-analysis.yml

- Trigger: `merge_group:`; `push: branches: [main, master]`; `pull_request: branches:
  [main, master]`; `schedule: cron '0 9 * * 1'`; `workflow_dispatch:`.
- Purpose: caller into the reusable `python-security-analysis.yml`, but with
  `run-codeql`, `run-dependency-review`, `run-osv`, and `run-bandit` all set `false` (those
  scans run elsewhere in this list); `security-gate-validation` then hard-fails the run if
  the `security` job's result is not `success`.
- Where to look when red: `Security Gate Validation` job first (fails if `needs.security.
  result != 'success'`); trace into the `security` job's own reusable-workflow run to find
  which sub-check inside `python-security-analysis.yml` actually failed, since the obvious
  scan flags are all disabled here.

### scorecard.yml

- Trigger: `branch_protection_rule:`; `schedule: cron '21 21 * * 2'` (Tuesday); `push:
  branches: [main, master]`; `workflow_dispatch:`.
- Purpose: caller into the reusable `python-scorecard.yml`, publishing this repo's OpenSSF
  Scorecard score.
- Where to look when red: the `scorecard` job needs `security-events: write` (SARIF
  upload) and `actions: read` (workflow metadata); check those grants first, then check the
  live dashboard at `https://securityscorecards.dev/viewer/?uri=github.com/
  ByronWilliamsCPA/.github` for which check regressed.

### dependency-provenance-weekly.yml

- Trigger: `schedule: cron '23 6 * * 1'` (Monday 06:23 UTC); `workflow_dispatch: inputs:
  python-version, open-issue`.
- Purpose: caller into the reusable `python-dependency-provenance.yml`, refreshing a
  sticky provenance issue against the latest OSV snapshot; this repo has no `uv.lock` or
  `package.json` so the scan itself no-ops, but the run proves the trigger and permission
  machinery still works.
- Where to look when red: per the file's own `#VERIFY` note, run `gh run list
  --workflow=dependency-provenance-weekly.yml` and confirm the conclusion is not
  `startup_failure`; a `startup_failure` means the caller's `permissions:` block (needs
  `contents: read` + `issues: write`) stopped granting what the reusable's post-issue job
  needs.

### sbom-nightly.yml

- Trigger: `schedule: cron '17 2 * * *'` (nightly, 02:17 UTC); `workflow_dispatch: inputs:
  python-version, fail-on-vulnerabilities, run-osv`.
- Purpose: caller into the reusable `python-sbom.yml`, pulling a fresh CVE database
  snapshot nightly so vulnerabilities disclosed between PR builds are caught within 24
  hours.
- Where to look when red: run `gh run list --workflow=sbom-nightly.yml` and confirm the
  conclusion is not `startup_failure` (the caller must grant `contents: read` +
  `security-events: write` for the reusable's SARIF-upload jobs); otherwise check Security
  > Code scanning alerts for a nightly-triggered entry on a distinct ref/sha.

### snyk-weekly.yml

- Trigger: `schedule: cron '43 3 * * 1'` (Monday 03:43 UTC); `workflow_dispatch: inputs:
  source-directory, run-oss, run-aibom, fail-on-high`.
- Purpose: two callers, `snyk` (into `python-snyk.yml`, Snyk Code/SAST against `scripts/`)
  and `snyk-iac` (into `python-snyk-iac.yml`, Terraform/IaC scan against `scripts/`).
  Deliberately weekly, not per-PR: Snyk hosted tests are metered against a monthly cap that
  per-PR scanning would exhaust.
- Where to look when red: first confirm `SNYK_TOKEN` is actually set (both reusables no-op
  cleanly when it is absent, so a red run means the token is present and Snyk found
  something, not a silent skip); then `gh run list --workflow=snyk-weekly.yml` to rule out
  `startup_failure` from a missing `security-events: write` grant.

## Release automation

### release-tag.yml

- Trigger: `push: branches: [main]`.
- Purpose: cuts a semver tag on every push to `main`, reading the merge commit message for
  Conventional Commits markers: `BREAKING CHANGE`/`!` bumps major, `feat:` bumps minor,
  everything else bumps patch. The tag is annotated and immutable (never updated or force
  pushed), satisfying the org's `ByronWilliamsCPA-tag-protection-semver` ruleset; consumers
  pin to the point tag or a 40-char SHA, never a floating major tag.
- Where to look when red: the `Compute next version and tag` step log has the computed
  `PREV`/`NEW_TAG` and the exact `git tag`/`git push` failure. A push rejection there
  usually means a tag for that version already exists (the job never force-pushes, so a
  collision fails loudly rather than silently overwriting); the job needs `contents:
  write`, check that grant if it fails before reaching the tag logic.
