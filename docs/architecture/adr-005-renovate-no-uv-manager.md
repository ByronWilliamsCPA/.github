# ADR-005: Never Add "uv" to Renovate's enabledManagers

**Status:** Accepted
**Date:** 2026-05-25

## Context

PR #149 added `"uv"` to `enabledManagers` in the org-default `renovate.json`,
on the reasoning that downstream repos using `uv.lock` needed a dedicated
manager to receive dependency-update PRs. This was based on a wrong mental
model of how Renovate handles `uv` projects, and it broke every downstream
repo that inherits this repo's `renovate.json` (`homelab-infra`, `gleif`,
`backpacking`, `williaby-claude`, `.claude`, `image-generation`,
`reference-library`, and any future `uv`-based repo).

Renovate (the version in use, v42.92.14 at the time) does not ship a manager
named `uv`. With `"uv"` present in `enabledManagers`, Renovate rejects the
**entire** org-default config with a validation error:

```text
Config validation errors found: The following managers configured in
enabledManagers are not supported: "uv"
```

This is not a partial failure. Every downstream repo stopped receiving any
Renovate updates at all, not just uv-related ones, until PR #151 reverted
the change the same day.

How `uv` is actually covered, without a dedicated manager:

1. **Dependency detection**: `uv` uses the standard PEP 621 `[project]`
   table in `pyproject.toml`. The existing `pep621` manager (already in
   `enabledManagers`) already finds these dependencies.
2. **Lockfile regeneration**: `uv.lock` regeneration is a self-hosted
   Renovate runner concern, not an org-default `renovate.json` concern; it
   is configured on the runner side (`homelab-infra`'s Renovate service),
   not in this repo.

`"uv"` is an intuitive but incorrect manager name for a uv-managed project;
more than one contributor has independently reached for it.

## Decision

Never add `"uv"` to `enabledManagers` in this repo's `renovate.json`.
`pep621` (already present) is sufficient for dependency detection in
uv-managed Python projects; `pip_requirements` and `github-actions` remain
as fallbacks for non-uv and Actions-based updates respectively. Lockfile
regeneration for `uv.lock` is a runner-side concern outside this repo's
scope.

## Consequences

- A future contributor proposing `"uv"` in `enabledManagers` should be
  pointed at PR #149 (the break) and PR #151 (the revert and full
  explanation) before the change is attempted again.
- Before adding any new value to `enabledManagers`, verify it against
  Renovate's actual supported-manager list; a single unsupported entry
  invalidates the whole config for every inheriting repo, not just the
  repos that would have used that manager.
- Any change to how `uv.lock` is regenerated belongs in the self-hosted
  Renovate runner's own configuration, not in this repo's `renovate.json`.
