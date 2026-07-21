# ADR-004: Retire the Floating v1 Tag; SHA Pins and Point Tags Only

**Status:** Accepted
**Date:** 2026-07-02

## Context

`refs/tags/v1` was originally intended as a moving major-version tag: consumer
repos would pin `@v1` and automatically receive every non-breaking update as
the tag was re-pointed forward. In practice the tag froze at `v1.1.0`
(`6f71aec`) the day the org's tag-protection ruleset
(`ByronWilliamsCPA-tag-protection-semver`) landed, since that ruleset blocks
update, delete, and non-fast-forward operations on `refs/tags/v*`. By the time
this was caught, `main` had advanced to `v7.0.1` while every `@v1` consumer,
including `renovate.json`'s own `followTag: "v1"` rule, docs, starter
templates, and two of this repo's own caller workflows (`scorecard.yml`,
`security-analysis.yml`), was still silently running v1.1.0-era workflow
code with none of the intervening security fixes (including the pre-#229
Trivy scanner update).

The floating-tag scheme was structurally incompatible with the tag-protection
ruleset that had already been adopted for other reasons; nothing in the
Renovate config or docs had been updated to reflect that.

## Decision

Commit fully to point-tag and SHA-pin versioning (matching CI-005 and
`release-tag.yml`'s stated policy); there is no floating major tag.

- Drop `followTag: "v1"` from `renovate.json` so Renovate advances
  org-workflow SHA pins to the latest immutable release tag instead of
  freezing at the dead tag reference. The org matcher was also tightened to
  an anchored `matchPackageNames` regex, replacing the deprecated unanchored
  `matchPackagePatterns` form (which could match lookalike repo names).
- Recommended caller syntax is `@<sha> # vX.Y.Z` (SHA pin with a
  release-tag comment; Renovate keeps it current). An immutable `@vX.Y.Z`
  point tag is acceptable where SHA pinning is impractical. `@main` is
  disallowed for production callers.
- Every live `@v1` reference across workflow headers, `docs/workflows/*.md`,
  `examples/*`, migration guides, and this repo's own callers was swept to
  the `v7.0.1` SHA-pin form. `docs/compliance/audits/` is intentionally left
  untouched as historical record.
- A new `no-floating-v1` pre-commit hook
  (`scripts/check-no-floating-v1.sh`) blocks any future bare floating major
  tag (`@v1`, `@v2`, ...) against an org-workflow reference, and blocks
  reintroducing `followTag` in Renovate config, with Bats coverage in
  `tests/check-no-floating-v1.bats`.
- `refs/tags/v1` was deleted org-wide on 2026-07-02 via a one-time admin
  ruleset bypass (org admins carry a standing `RepositoryRole-5`
  always-bypass on the tag-protection ruleset for exactly this kind of
  one-time maintenance operation), after confirming no live `@v1` callers
  remained.

## Consequences

- Consumers must pin to a specific SHA or an immutable point tag; there is
  no "get the latest minor/patch automatically" tag to lean on. Renovate is
  the intended mechanism for keeping SHA pins current.
- Any straggler consumer still referencing `@v1` now fails loudly (the ref
  no longer resolves) instead of silently running frozen, unpatched
  workflow code. This is deliberate: `update-pinned-actions.sh --pin-tags`
  intentionally skips first-party `@v1` refs, so the loud failure is the
  detection mechanism for stragglers, not a bug.
- `enabledManagers` and `matchPackageNames` config changes in
  `renovate.json` apply org-wide; any downstream repo relying on the old
  unanchored pattern-match behavior would need to re-verify its own
  Renovate rules.
- Follow-up (tracked outside this repo): the `.claude` repo's
  `devops-deployment-agent.md` standards-manifest check (CI-057) needed a
  matching inversion, since it previously asserted `followTag: "v1"` should
  be *present*; that was corrected in `.claude` commit `ac1df86`. Consumer
  repos and the cookiecutter template that still replicate a `followTag`
  rule locally should have it removed as a separate cleanup pass.
