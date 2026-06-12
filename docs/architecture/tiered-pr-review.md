# Tiered PR Review Architecture: Reference for Reviewers

Status: proposed (this document ships with the PR that introduces Tier 0)
Date: 2026-06-12
Owners: ByronWilliamsCPA (solo maintainer)
Scope: ByronWilliamsCPA/.github first; fleet-wide after tuning

## 1. Purpose and audience

This document briefs every reviewer of the tiered-review change on what is
changing and why, so review feedback lands on the decisions that matter. It
is written for all parties that review PRs in this org:

- The Claude side: the `/pr-review` and `/pr-fix` skill pipeline maintained
  in `ByronWilliamsCPA/.claude` (`.claude/skills/pr-review/`), and any
  Claude Code session asked to review this PR.
- The GitHub side: Copilot code review, CodeRabbit, and the repo's own CI
  gates (pre-commit, actionlint, shell-tests, PR validation).
- The human maintainer.

## 2. Background: the review stack today

Every PR in this repo currently gets, in rough order:

1. Static CI: pre-commit lint suite, actionlint plus shellcheck self-test,
   Bats and pytest suites, conventional-commit title validation, CodeQL,
   secret scanning.
2. Async AI reviewers: Copilot code review (auto-enrolled) and CodeRabbit
   comment on the diff.
3. Optionally, the deep pass: the maintainer manually runs the
   `/pr-review` skill, which aggregates Copilot, CodeRabbit, SonarQube, and
   CI into confidence-scored, deduplicated, consensus-validated findings
   (13 specialized agents, a premise gate, four severity tiers), and
   `/pr-fix` to remediate.

Constraints that shape the design:

- Solo maintainer. Required human approvals are intentionally disabled
  (see `docs/compliance-reports/manual-actions.md`); automation is the
  review capacity.
- The deep pass is expensive (multi-agent, Opus-class consensus) and
  manual. PRs that never get it are gated only by the static layer and raw
  bot comments.
- Analysis of the last 60 PRs (#141 to #210) shows roughly half the traffic
  does not warrant the deep pass: ~18% Renovate action-pin bumps, ~17%
  mechanical pattern-series fixes that cite a precedent PR, ~7% docs-only,
  ~10% config tweaks. The substantive remainder is where deep review has
  demonstrably paid off (PR #175's review produced two follow-up PRs of
  findings, #176 and #177).

## 3. The change: a two-tier review system

### Tier 0 (new, this PR): universal automated baseline

`.github/workflows/claude-baseline-review.yml` runs on every non-draft PR
targeting `main`. It is a single capped `claude-code-action` pass
(Sonnet 4.6, max 30 turns, 15-minute timeout) that:

1. Classifies the PR into one of five classes:

   | Class | Signal | Spot check performed |
   |-------|--------|----------------------|
   | renovate-deps | `renovate/*` branch, `automated`/`dependencies` labels | Verify every changed action pin: the tag named in the trailing comment must resolve to the pinned SHA (annotated tags dereferenced). Flag major version jumps. |
   | pattern-series | Body cites a precedent PR with the same pattern | Diff against the precedent; flag deviations only |
   | docs-only | Only Markdown / `docs/` changes | Factual accuracy, link validity, em-dash rule, CHANGELOG need |
   | config-tweak | Tool config only, no workflow logic | Semantics of changed keys, motivation stated |
   | substantive | Everything else | Focused diff review: logic errors, swallowed failures, expression injection into `run:` blocks, permission widening, secret handling, description-vs-diff accuracy |

2. Posts ONE sticky comment (marker `<!-- claude-baseline-review -->`) with
   a verdict: `BASELINE-OK` or `ESCALATE`, findings (if any), and the
   status of Copilot, CodeRabbit, and CI at review time.
3. On `ESCALATE`, applies the `needs-deep-review` label. That label is the
   queue for Tier 1.

Escalation is deterministic where possible. Any one of these forces
`ESCALATE`:

1. Changes under `.github/workflows/` or `workflow-templates/` touching
   `permissions:`, secrets, `id-token`, `on:` triggers, or `workflow_call`
   inputs.
2. Changes under `scripts/` that write via `gh api`, handle secrets, or
   transfer/delete resources.
3. `breaking-change` label or `!` in the conventional-commit title.
4. More than 500 changed lines (excluding lockfiles, `checksums.txt`,
   generated files).
5. Any renovate tag/SHA mismatch, or a major action update.
6. Reviewer judgment: security-sensitive or architectural implications a
   one-pass review cannot clear.

Docs-only changes, pattern-series PRs matching their precedent, and clean
patch/minor pin bumps do not escalate on their own.

### Tier 1 (existing, unchanged by this PR): the pr-review skill

The `/pr-review` and `/pr-fix` pipeline in `ByronWilliamsCPA/.claude` is
not modified. What changes is its triggering economics: instead of the
maintainer deciding per-PR whether to run it, the `needs-deep-review`
label provides a curated queue. Estimated effect based on the 60-PR
sample: deep review effort concentrates on the ~40-45% of PRs where it has
historically found real issues.

## 4. Security model of Tier 0

Reviewers should hold this PR to the repo's existing workflow standards.
Key properties, in the order an auditor would check them:

- Advisory only. The job never blocks a merge; the verdict is a comment
  plus a label. A failed job (for example, missing API key) does not gate
  other checks.
- Permissions: workflow-level `permissions: {}`; the single job requests
  `contents: read` (checkout only), `pull-requests: write` (sticky comment,
  label), `issues: write` (label API paths; flagged `#VERIFY` for later
  narrowing), and `id-token: write` (OIDC exchange for the Claude GitHub
  App token). RAD tags in the file document each scope.
- All three actions SHA-pinned with tag comments, per repo policy.
  `anthropics/claude-code-action` is pinned to v1.0.145
  (`ebcdfe6dc6bb7511eb63e59e07df256dbcf59a2e`); the pin was verified
  against the upstream release before committing.
- `persist-credentials: false` on checkout; harden-runner (egress audit)
  as the first step, matching every other workflow in this repo.
- Prompt-injection posture: only `github.repository` and the PR number are
  interpolated into the prompt (trusted event context). PR title, body,
  diff, and comments are fetched by the agent as data; the prompt
  instructs the agent to treat them as untrusted and to report, not
  follow, embedded instructions. The agent is comment-only: no pushes, no
  approvals, no code execution beyond the allowlisted `gh` reads.
- Tool allowlist is deliberately narrow: `gh pr view/diff/comment/edit`,
  `gh api repos/*` (tag and commit reads for pin verification),
  `gh label`. Notably `gh pr` is NOT allowlisted wholesale because that
  would include `gh pr merge`.
- Cost containment: concurrency group cancels superseded runs;
  `--max-turns 30`; `timeout-minutes: 15`.

## 5. What does not change

- All existing CI gates, their ordering, and their blocking behavior.
- Copilot and CodeRabbit enrollment and behavior. Tier 0 consumes their
  output; it does not replace them.
- The pr-review skill's content, agents, scoring, or fix workflow.
- Branch and tag rulesets, merge queue behavior, Renovate/Dependabot
  configuration.

## 6. Division of ownership

| Concern | Lives in | Why |
|---------|----------|-----|
| Tier 0 workflow, escalation policy, label semantics | `ByronWilliamsCPA/.github` (this PR) | It is CI policy, versioned with the other org workflows |
| Tier 1 skill (agents, scoring, premise gate, fixes) | `ByronWilliamsCPA/.claude` | Already the global Claude config repo, symlinked into `~/.claude` locally |
| Planned: baseline mode inside the skill | `ByronWilliamsCPA/.claude` | Phase 4 below replaces the prompt-encoded baseline with `/pr-review --baseline` so both tiers share one codebase and one set of tunable thresholds |

Known limitation worth reviewer attention: until the `.claude` repo is
consumable in CI (plugin marketplace packaging), the Tier 0 prompt in this
workflow and the skill's classification logic are separate
implementations of overlapping rules. They can drift. Phase 4 removes the
duplication; until then, changes to either side should cross-reference the
other.

## 7. Rollout plan

| Phase | Scope | Gate to next phase |
|-------|-------|--------------------|
| 1 (this PR) | Repo-local, advisory, this repo only | `ANTHROPIC_API_KEY` secret and Claude GitHub App configured; several weeks of verdicts reviewed for precision |
| 2 | Tune: escalation thresholds, comment format, label taxonomy | False-escalation and missed-escalation rates acceptable to the maintainer |
| 3 | Promote to a `workflow_call` reusable consumed by fleet repos | Same conventions as the other `python-*` reusables; templates plus docs |
| 4 | Replace the prompt-encoded baseline with a skill-native baseline mode invoked headlessly from CI | `.claude` repo packaged as a plugin marketplace; skill gains a non-interactive mode |

## 8. Setup prerequisites (phase 1)

1. Repository (or org) secret `ANTHROPIC_API_KEY`.
2. Claude GitHub App installed on the repo for OIDC token exchange, OR a
   `github_token` input supplied to the action (then drop
   `id-token: write`).

Until both exist, the job fails at startup; because the workflow is
advisory, nothing else is affected.

## 9. Questions reviewers can most usefully answer

1. Escalation rules: is anything missing from the deterministic list in
   section 3 that should force a deep review in this repo? Is anything
   listed that will fire so often it makes `needs-deep-review` noise?
2. Tool allowlist: is any allowlisted `gh` surface wider than the job's
   token permissions make safe? Is `gh api repos/*` acceptable given the
   token's scopes bound the blast radius?
3. Advisory vs blocking: should a renovate tag/SHA mismatch (a genuine
   supply-chain signal) fail the check rather than merely escalate?
4. Label semantics: is a single `needs-deep-review` label sufficient, or
   should escalation reasons be encoded (for example,
   `escalate:supply-chain`, `escalate:permissions`)?
5. Drift risk in section 6: acceptable for phases 1 to 3, or should phase
   4 be pulled earlier?

## 10. References

- Workflow under review: `.github/workflows/claude-baseline-review.yml`
- CHANGELOG entry: `CHANGELOG.md` (Unreleased / Added)
- Tier 1 skill: https://github.com/ByronWilliamsCPA/.claude/tree/main/.claude/skills/pr-review
- Action: https://github.com/anthropics/claude-code-action (docs:
  https://code.claude.com/docs/en/github-actions)
- Traffic analysis basis: PRs #141 to #210 of this repo; deep-review value
  evidence: #175 review producing #176 and #177
- Repo workflow standards: `.claude/CLAUDE.md` (RAD tagging, writing
  rules), `docs/audit/2026-05-29/00-final-report.md` (baseline audit)
