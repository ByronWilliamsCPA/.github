# 01 - Dependencies and Supply Chain

HEAD e070932. The action pinning posture is strong: 57 distinct third-party/org actions, all referenced by full 40-character commit SHA with a trailing version comment, across 34 workflow files and 33 templates. The notable defects are one `@master` pin in a workflow template, three Git submodules with no commit pin in `.gitmodules` (tracking default branches over plain HTTPS), and a workflow-template Python matrix that targets `3.14` (not a released CPython as of the knowledge cutoff). No requirements/setup.py/poetry/pyproject residue exists anywhere in the tree, consistent with a package-free reusable-workflow repo.

## Findings

**DEP-01: One action pinned to a moving branch (`@master`) in a template**
- Severity: High
- Effort: S (single-line edit, basis: replace one ref with the SHA already used in production)
- Evidence: `workflow-templates/python-sonarcloud.yml:103` uses `sonarsource/sonarqube-quality-gate-action@master`. The production copy at `.github/workflows/python-sonarcloud.yml:411` pins the same action to `cf038b0e0cdecfa9e56c198bbb7d21d751d62c3b # v1.2.0`. Confirmed via `grep -rnE 'uses: [^ ]+@[a-zA-Z0-9._-]+' ... | grep -vE '@[a-f0-9]{40}' | grep -vE '@v?[0-9]'` returning exactly one non-comment hit.
- Recommendation: Pin the template line to the same SHA (`cf038b0e...` / v1.2.0) used in the production workflow so consumers who copy the template inherit a SHA pin, not a branch.

**DEP-02: Git submodules unpinned in `.gitmodules` and uninitialized**
- Severity: High
- Effort: S (add `branch`/commit discipline; basis: config edit plus a fetch policy decision)
- Evidence: `.gitmodules:1-9` declares bats-core, bats-support, bats-assert with `url = https://github.com/bats-core/...` and no `branch =` or pinned ref. `git submodule status` shows all three with a `-` prefix (uninitialized): `-3bca150...bats-core`, `-f1e9280...bats-assert`, `-24a72e14...bats-support`. The gitlink SHAs live in the index, not in `.gitmodules`, so a fresh `git submodule add`/update against these URLs tracks the upstream default branch. The Bats suite under `tests/` (run by `.github/workflows/shell-tests.yml`) depends on these.
- Recommendation: The committed gitlink SHAs do pin the checked-out commit, so reproducibility is preserved for `submodule update --init`; the risk is operational (uninitialized = shell tests cannot run locally/CI without an init step) and supply-chain (no `branch` discipline, plain HTTPS to a third-party org). Document the required `git submodule update --init` step and consider vendoring or a checksum gate on the bats libraries.

**DEP-03: Workflow-template Python matrix targets unreleased `3.14`**
- Severity: Medium
- Effort: S (matrix edit, basis: one-line list change)
- Evidence: `workflow-templates/python-ci.yml:138` sets `python-version: ["3.10", "3.11", "3.12", "3.13", "3.14"]`. CPython 3.14 is not a released stable version as of the January 2026 knowledge cutoff (3.13 is current); whether 3.14 has since shipped cannot be confirmed without network. `setup-python` resolving `3.14` against a runner toolcache that lacks it will fail or silently pull a pre-release. The reusable callee `.github/workflows/python-compatibility.yml` documents the supported set as `["3.10", "3.11", "3.12", "3.13"]` (line 11), so the template is one version ahead of the library's own declared range.
- Recommendation: Either drop `3.14` from the template matrix or mark it `allow-prereleases`/non-gating until 3.14 reaches stable, to keep the template green for consumers.

**DEP-04: Stale-pin verification is bounded by no-network**
- Severity: Low
- Effort: M (recurring; basis: requires GitHub API access to compare each SHA against latest tag)
- Evidence: All 57 actions carry version comments (e.g. `actions/checkout@de0fac2e... # v6.0.2`, `step-security/harden-runner@ab7a9404... # v2.19.3`, `actions/upload-artifact@043fb46d... # v7.0.1`, `aquasecurity/trivy-action@ed142fd0... # v0.36.0`). Whether each pinned SHA is the newest within its major (i.e. staleness) cannot be determined here: shellcheck/actionlint/network tooling is unavailable, so latest-release dates and tag-to-SHA mappings are not verifiable offline. The repo ships `scripts/update-pinned-actions.sh` (scans workflows, fetches latest same-major SHA via GitHub API, dry-run by default) and `scripts/fleet-audit-sha-pins.sh` for exactly this; Renovate (`renovate.json`) also runs github-actions with `pinDigests: true` and auto-merge for minor/patch.
- Recommendation: Run `scripts/update-pinned-actions.sh` (dry-run) or rely on the Renovate dashboard to confirm no pin trails its major by more than one minor; no manual action needed beyond confirming Renovate is enabled on the repo.

**DEP-05: Pre-commit hooks SHA-pinned; version comments consistent**
- Severity: Low
- Effort: S (verification only)
- Evidence: `.pre-commit-config.yaml` pins all five remote repos to 40-char revs with version comments: pre-commit-hooks `c4a0b88 # v4.5.0` (line 8), commitizen `9707a58 # v4.16.0` (25), yamllint `cba56bc # v1.38.0` (34), markdownlint-cli `e72a3ca # v0.48.0` (43), detect-secrets `01886c8 # v1.5.0` (52), trufflehog `05cccb5 # v3.92.3` (68). Release dates for these revs cannot be confirmed offline. pre-commit-hooks v4.5.0 is an older line (v5.x exists in the v4/v5 series); confirm against upstream when network is available.
- Recommendation: Keep SHA pinning; add pre-commit repos to the Renovate `pre-commit` manager (not currently in `enabledManagers`, which lists only pep621/pip_requirements/github-actions) so hook revs get the same automated bump as actions.

**DEP-06: SBOM workflow scope is sound for a package-free repo**
- Severity: Low
- Effort: S (informational)
- Evidence: `.github/workflows/python-sbom.yml` (CycloneDX SBOM generation plus Trivy, OSV-Scanner, Grype gates, header lines 15-23) and `.github/workflows/sbom-nightly.yml` (cron `17 2 * * *`, calls `./.github/workflows/python-sbom.yml`). The nightly header (lines 5-6) states the org self-test "skips cleanly here (no pyproject.toml in .github)" and exists to keep the trigger machinery live and refresh the CVE DB nightly. `docs/known-vulnerabilities.md` confirms "This repo has no Python package and no container images" and lists no open CVEs as of 2026-05-14.
- Recommendation: No change. The SBOM produces no package manifest for this repo by design; it serves as a live self-test of the reusable workflow that downstream package repos consume.

**DEP-07: No migration residue, no base-image pins to manage**
- Severity: Low
- Effort: S (informational)
- Evidence: `find` for `requirements*.txt`, `setup.py`, `setup.cfg`, `poetry.lock`, `Pipfile*`, `pyproject.toml`, `uv.lock` across the whole tree returned nothing. No Dockerfile exists (`find -iname '*dockerfile*'` empty). All jobs use `runs-on: ubuntu-latest`; no `container:`/`image:`/`FROM` base-image pins are present (the `python-container-security.yml` `build-image` input builds a consumer's Dockerfile at call time, not one in this repo). Real Python matrices bottom out at 3.10 (Python 3.8 EOL 2024-10 and 3.9 EOL 2025-10 are not targeted anywhere); 3.13 is current.
- Recommendation: None. Clean sub-area.

## Backlog rows (for orchestrator)

DEP-01 | Action pinned to moving `@master` branch in template | domain=dependencies | High | S | workflow-templates/python-sonarcloud.yml | line 103 `sonarsource/sonarqube-quality-gate-action@master`; production copy pins same action to SHA cf038b0e (v1.2.0) at python-sonarcloud.yml:411 | Pin template line to SHA cf038b0e / v1.2.0 to match production | none
DEP-02 | Git submodules unpinned in .gitmodules and uninitialized | domain=dependencies | High | S | .gitmodules; tests/libs/bats-core; tests/libs/bats-support; tests/libs/bats-assert | .gitmodules:1-9 no branch/ref over HTTPS; `git submodule status` shows `-` prefix on all three; gitlink SHAs only in index | Document `submodule update --init` step; add branch discipline or checksum gate on bats libs | none
DEP-03 | Workflow-template Python matrix targets unreleased 3.14 | domain=dependencies | Medium | S | workflow-templates/python-ci.yml | line 138 matrix `[3.10..3.14]`; 3.14 not stable as of Jan 2026 cutoff; callee declares max 3.13 at python-compatibility.yml:11 | Drop 3.14 or set allow-prereleases/non-gating until stable | none
DEP-04 | Action pin staleness unverifiable offline | domain=dependencies | Low | M | .github/workflows/*.yml; workflow-templates/*.yml; scripts/update-pinned-actions.sh; scripts/fleet-audit-sha-pins.sh; renovate.json | 57 distinct SHA-pinned actions all carry version comments; no network to confirm latest-within-major | Run update-pinned-actions.sh dry-run or confirm Renovate enabled | none
DEP-05 | Pre-commit hooks SHA-pinned; not in Renovate managers | domain=dependencies | Low | S | .pre-commit-config.yaml; renovate.json | hooks pinned rev+comment lines 8,25,34,43,52,68; renovate enabledManagers lacks pre-commit; pre-commit-hooks at v4.5.0 (older line) | Add pre-commit manager to Renovate; confirm hook revs current when network available | none
DEP-06 | SBOM workflow scope sound for package-free repo | domain=dependencies | Low | S | .github/workflows/python-sbom.yml; .github/workflows/sbom-nightly.yml; docs/known-vulnerabilities.md | sbom-nightly cron 17 2 * * * calls python-sbom; header notes clean skip (no pyproject); known-vuln doc clean as of 2026-05-14 | No change; serves as live self-test of reusable workflow | none
DEP-07 | No migration residue or base-image pins | domain=dependencies | Low | S | (repo-wide) | find for requirements/setup.py/poetry/Pipfile/pyproject/uv.lock empty; no Dockerfile; all jobs ubuntu-latest; matrices bottom at 3.10 | None; clean sub-area | none
