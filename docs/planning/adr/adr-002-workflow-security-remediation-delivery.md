# ADR-002: Workflow Security Remediation Delivery Strategy

**Status:** Accepted
**Date:** 2026-04-30
**Deciders:** Byron Williams
**Source spec:** `docs/superpowers/specs/2026-04-30-workflow-security-architecture-remediation-design.md`

---

## TL;DR

Three sequential PRs deliver security fixes, architecture cleanup, and new capabilities in strict dependency order. PR 1 uses two parallel worktrees merged before the PR opens. All breaking changes use hard removal with in-file migration notes rather than deprecation shims.

---

## Context

A three-domain audit of 23 reusable org-level GitHub Actions workflows identified:
- 2 critical RCE/injection vectors (arbitrary Python execution, heredoc input interpolation)
- 6 high findings (permission over-scoping, shell injection via unquoted inputs)
- Multiple medium findings (egress policy, artifact integrity, false-assurance gates)
- Architecture gaps (SonarCloud/Codecov duplication, wrong org references, missing workflows)
- Supply chain gaps (Docker provenance off by default, unpinned security tools)

The remediation spans 23 files and mixes critical security fixes with breaking architectural changes.

---

## Decision

### D1: Three sequential PRs with hard dependency gates

| PR | Focus | Breaking |
|---|---|---|
| 1 | Security fixes + supply chain | Soft (Docker defaults flip) |
| 2 | Architecture cleanup | Yes -- callers must migrate |
| 3 | New capabilities | No |

Each PR requires the previous to merge to `main` before branching. This isolates breaking architecture changes from security fixes and makes each PR independently reviewable.

**Rejected alternative:** Single large PR -- too wide for safe review; security fixes and breaking architecture changes interact unpredictably in a combined diff.

**Rejected alternative:** Many small PRs per finding -- review overhead exceeds value; related fixes (e.g., all input-quoting changes) belong together for atomic validation.

### D2: Parallel worktrees for PR 1

PR 1 has two logically independent change sets:
- Worktree A (`fix/perf-regression-rce`): `python-performance-regression.yml` only (CRIT-01, CRIT-02)
- Worktree B (`fix/workflow-input-quoting`): systematic env-var sweep across ~12 files + supply chain

Both worktrees merge into `fix/workflow-security-remediation` before the PR opens. Worktree paths follow the `.worktrees/<branch-slug>` convention required by CLAUDE.md.

**Rejected alternative:** Sequential worktrees -- the CRIT fixes and the sweep are independent; parallel saves implementation time.

### D3: Hard removal with migration notes (no deprecation shims)

SonarCloud, Codecov, and `python-pr-validation.yml` are removed entirely rather than gated behind deprecation flags. Breaking callers receive:
- Migration comments in the affected workflow headers
- A hard-fail job in `python-pr-validation.yml` that exits 1 with a migration message on every trigger

**Rejected alternative:** Deprecation path with `enable-sonarcloud` flag kept for one release cycle -- adds dead code, complicates the architecture cleanup PR, and signals that removal is negotiable.

### D4: Supply chain fixes bundled with security PR (PR 1)

Docker provenance defaults, pip-audit replacement, and SLSA template fixes are security-adjacent and are delivered in PR 1 alongside the shell-injection and Python-injection fixes.

**Rejected alternative:** Defer supply chain to PR 2 -- no justification for deferring security posture improvements when they are already scoped.

### D5: Env-var isolation as the canonical input-sanitization pattern

All inputs used in `run:` shell blocks or Python heredocs must be declared in an `env:` block and referenced via `$VAR` (shell) or `os.environ["VAR"]` (Python). Direct `${{ inputs.* }}` interpolation in `run:` blocks is prohibited.

This pattern is applied systematically across all 23 workflows in PR 1 and is the required pattern for all new workflows in PR 3.

---

## Consequences

**Positive:**
- Security critical findings resolved in the first PR, before any architecture work
- Breaking changes isolated to PR 2 with clear migration notes; callers can prepare
- Env-var isolation pattern is consistent across all 23 workflows after PR 1
- New workflows in PR 3 inherit the hardened pattern by default

**Negative:**
- Callers using `enable-sonarcloud`, `enable-codecov`, or `python-pr-validation.yml` break on PR 2 merge with no gradual migration window
- Docker `enable-sbom` default flip in PR 1 may increase artifact storage costs for callers who set it to false intentionally

**Risks:**
- Merge conflicts between Worktree A and Worktree B outputs if both touch the same workflow; mitigated by scope restriction (Worktree A touches only `python-performance-regression.yml`)
- actionlint/shellcheck must validate all modified YAML before each commit; missed by CI if `qlty check` is not run locally
