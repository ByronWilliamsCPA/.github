# ADR-001: Scorecard publish_results: false in Reusable Workflow

**Status:** Accepted
**Date:** 2026-05-14

## Context

The `python-scorecard.yml` reusable workflow hard-codes `publish_results: false`.
When a reusable workflow calls `ossf/scorecard-action`, the OIDC token `repository`
claim resolves to the calling repo (e.g., `ByronWilliamsCPA/some-python-project`),
which is correct. However, Scorecard's API lookup uses this claim to attribute results.
When the reusable workflow itself is tested in the `.github` repo via `self-test.yml`,
the OIDC token resolves to `ByronWilliamsCPA/.github`, which does match the repo we
want to score. The constraint is `publish_results: true` in the reusable workflow would
expose results for every calling repo under a single API entry.

## Decision

Keep `publish_results: false` in `python-scorecard.yml` (the reusable workflow).
Add a direct, non-reusable `self-scorecard` job to `scorecard.yml` in this repo
that uses `publish_results: true`. This job runs the scorecard action directly
(not via the reusable), so the OIDC token `repository` claim correctly resolves to
`ByronWilliamsCPA/.github`.

## Consequences

- Downstream repos using `python-scorecard.yml` do not publish results (by design;
  they opt in by adding their own scorecard workflow).
- The `.github` repo itself publishes results via the direct job.
- The reusable workflow remains unchanged for callers.
