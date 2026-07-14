# Claude Baseline Review (Tier 0 PR Triage)

Reusable `workflow_call` workflow that runs a single capped Claude Code Action pass over
every non-draft, same-repo pull request, classifies it, runs class-appropriate spot
checks, and posts one sticky verdict comment (`BASELINE-OK` or `ESCALATE`). On
`ESCALATE` it applies the `needs-deep-review` label, which queues the PR for a deeper,
human-invoked review pass. The verdict is advisory: it never blocks a merge, and it
fails only on operational errors such as a missing secret.

For the design rationale, the two-tier review architecture, and the full security
analysis (prompt-injection posture, tool-allowlist reasoning, tamper protection), see
[docs/architecture/tiered-pr-review.md](../architecture/tiered-pr-review.md). This page
covers how to call the workflow; it does not repeat that narrative.

## Quick Reference

**Workflow**: `.github/workflows/claude-baseline-review.yml`
**Type**: Reusable (`workflow_call`)
**Security model**: advisory-only AI reviewer; the caller job's permission scopes and
the action's `--allowedTools` allowlist are the enforced CI boundary, not this repo's
local `.claude/settings.json` (that file hardens interactive sessions only).

## When to use this workflow

Call it from a thin per-repo caller triggered on `pull_request` when you want a fast,
class-appropriate triage comment on every PR so a maintainer (or a downstream label
queue) can decide whether a deeper review pass is warranted.

## When NOT to use it

- You need a blocking/gating review. This workflow never fails a PR on `ESCALATE`; it
  only fails on operational errors (auth, action failure).
- The consuming repo has no `ANTHROPIC_API_KEY` secret available and no Claude GitHub
  App installed. The job fails at startup until both exist.
- You expect fork PRs to be reviewed. The job condition skips fork PRs by design,
  since `pull_request` runs from forks cannot read the API-key secret.

## Minimal usage

Adapted from this repo's own caller,
[`.github/workflows/claude-baseline-review-pr.yml`](../../.github/workflows/claude-baseline-review-pr.yml):

```yaml
name: Claude Baseline Review (PR)

on:
  pull_request:
    types: [opened, synchronize, reopened, ready_for_review, edited]
    branches:
      - main

permissions: {}

jobs:
  review:
    permissions:
      contents: read
      pull-requests: write
      issues: write
      id-token: write
    uses: ByronWilliamsCPA/.github/.github/workflows/claude-baseline-review.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1
    with:
      repo-description: >-
        a one or two sentence description of what this repository contains.
      sensitive-paths: '.github/workflows/, scripts/'
      escalation-guidance: |
        - Changes that touch permissions, secrets, or authentication.
        - Changes to build or release automation.
    secrets: inherit  # pragma: allowlist secret
```

## Inputs

| Input | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `repo-description` | string | Yes | none | One or two sentences describing the consuming repository, injected into the reviewer prompt as context so classification reflects what the repo actually contains. |
| `sensitive-paths` | string | Yes | none | Comma or space separated path prefixes whose modification forces the substantive class (and therefore the full spot checks). Example for a workflow library: `.github/workflows/, workflow-templates/, scripts/`. |
| `escalation-guidance` | string | Yes | none | Repo-specific escalation triggers, appended verbatim to the universal trigger list in the prompt. Plain text describing change types that must force a deep review in this repo (for example, edits to executable hooks, permission or deny config, or secret handling). |

All three inputs are required; there are no defaults, since the prompt is shared
across every consuming repo and relies on caller-supplied framing to stay accurate.

## Secrets

| Secret | Required | Description |
|--------|----------|--------------|
| `ANTHROPIC_API_KEY` | Yes | Claude API key for the baseline reviewer. In this org it is an org-level secret (visibility: all), so callers typically pass it through with `secrets: inherit` rather than defining a per-repo secret. |

## Required Permissions

A called reusable workflow runs with a token bounded by the caller job's permissions,
so the scopes below are the ceiling the reusable needs; the caller must grant all four
or the run fails at startup:

```yaml
permissions:
  contents: read        # checkout only; the reviewer never pushes
  pull-requests: write   # sticky verdict comment, label application
  issues: write          # label create/add paths route through the Issues API
  id-token: write        # OIDC exchange for a short-lived Claude GitHub App token
```

This permission ceiling, combined with the action's `--allowedTools` allowlist (`gh pr
view/diff/comment/edit`, two read-only `gh api` tag-resolution endpoints, and `gh label
create` for the single escalation label), is the actual security boundary for an
agent-in-CI workflow: no `contents: write` and no mutating `gh api` verb is reachable
regardless of what the prompt says or what a PR's untrusted content contains. Do not
widen any of these four scopes without updating the security analysis in
[docs/architecture/tiered-pr-review.md](../architecture/tiered-pr-review.md).

If the Claude GitHub App is not installed on the consuming repo, pass a `github_token`
input to the action instead and drop `id-token: write` (this requires a fork of the
prompt step in the reusable; the current reusable only wires up the OIDC path).

## Troubleshooting

### Job fails at startup with an auth or token-exchange error

**Symptoms**: the "Run baseline triage review" step fails immediately, before any
`gh` calls, with an authentication or OIDC exchange error.

**Solutions**:

1. Confirm `ANTHROPIC_API_KEY` is set as an org or repo secret and is reachable from
   the caller (`secrets: inherit` or an explicit `secrets:` block).
2. Confirm the Claude GitHub App is installed on the consuming repository (required
   for the `id-token: write` OIDC exchange).
3. Confirm the caller job grants all four permissions listed above; a missing
   `id-token: write` fails the exchange even with a valid API key.

### Fork pull requests are never reviewed

**Expected behavior**: the job's `if:` condition skips any PR whose head repository is
not the base repository. This is by design, since `pull_request` runs triggered from a
fork cannot read `secrets.ANTHROPIC_API_KEY`; without the gate every fork PR would fail
at startup instead of being silently skipped.

**Action**: none needed for same-repo workflows. If your repo relies on fork PRs, this
workflow will not cover them; route fork PRs through a manual or `pull_request_target`
review path instead.

### `needs-deep-review` label never appears after an ESCALATE verdict

**Symptoms**: the sticky comment reads `ESCALATE`, but the label is missing from the
PR, or the comment itself notes the label could not be applied.

**Solutions**:

1. Confirm the caller grants `issues: write` in addition to `pull-requests: write`;
   label creation and assignment can route through the Issues API even on pull
   requests.
2. Check whether the label `needs-deep-review` already exists with a conflicting
   description or color; the reviewer treats "already exists" as non-fatal but other
   `gh label create` failures are not swallowed silently, the comment surfaces them as
   an Important finding.

### Reviewer comment is stale or missing after a PR body edit

**Expected behavior**: the reusable intentionally skips bot-initiated `edited` events
(for example, CodeRabbit editing the PR body) to avoid an OIDC exchange failure on
every automated edit. Only human-initiated `edited` events re-trigger reclassification.

**Action**: if you need re-classification after a specific bot edit, re-run the check
manually or push a trivial commit to trigger `synchronize` instead.
