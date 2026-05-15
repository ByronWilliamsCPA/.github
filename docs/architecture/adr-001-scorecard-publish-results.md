# ADR-001: Scorecard publish_results: false in Reusable Workflow

**Status:** Proposed
**Date:** 2026-05-14

## Context

The `python-scorecard.yml` reusable workflow hard-codes `publish_results: false`.
When a reusable workflow calls `ossf/scorecard-action`, the OIDC token `repository`
claim resolves to the `.github` repo (where the workflow file lives), not the calling
repository. The scorecard-action uses that claim to publish results to
securityscorecards.dev. With the wrong repo claim, publication fails and the job
errors. The reusable workflow keeps `publish_results: false` to prevent this; SARIF
upload to the calling repo's Security tab continues to work correctly.

## Decision

Keep `publish_results: false` in `python-scorecard.yml` (the reusable workflow).
Add a direct, non-reusable `self-scorecard` job to `scorecard.yml` in this repo
that uses `publish_results: true`. This job runs the scorecard action directly
(not via the reusable), so the OIDC token `repository` claim correctly resolves to
`ByronWilliamsCPA/.github`.

**Implementation deferred to Task 5 (OSSF/Scorecard PR).**

## Consequences

- Downstream repos using `python-scorecard.yml` do not publish results (by design;
  they opt in by adding their own scorecard workflow).
- The `.github` repo itself publishes results via the direct job.
- The reusable workflow remains unchanged for callers.
