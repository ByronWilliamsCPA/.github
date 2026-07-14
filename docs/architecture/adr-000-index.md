# Architecture Decision Records

Index of ADRs for the ByronWilliamsCPA/.github reusable workflow library.

| ADR                                             | Title                                                              | Status   | Date       |
|-------------------------------------------------|--------------------------------------------------------------------|----------|------------|
| [ADR-001](adr-001-scorecard-publish-results.md) | Scorecard publish-results deprecated; action param hardcoded false | Accepted | 2026-05-14 |
| [ADR-002](adr-002-workflow-security-remediation-delivery.md) | Workflow security remediation delivery strategy | Accepted | 2026-04-30 |
| [ADR-003](adr-003-snyk-ai-code-security.md) | Snyk AI code security adoption | Accepted | 2026-06-24 |
| [ADR-004](adr-004-retire-floating-v1-tag.md) | Retire the floating v1 tag; SHA pins and point tags only | Accepted | 2026-07-02 |
| [ADR-005](adr-005-renovate-no-uv-manager.md) | Never add "uv" to Renovate's enabledManagers | Accepted | 2026-05-25 |

## ADR Format

Each ADR covers: Context, Decision, Consequences.
Use status: Proposed / Accepted / Deprecated / Superseded.

All ADRs live in `docs/architecture/`. `docs/planning/` is for active plans
and roadmaps only, not decision records.

## Reference Documents

Architecture references that are not decision records (no Context/Decision/Consequences format):

| Document | Title | Status | Date |
|----------|-------|--------|------|
| [tiered-pr-review](tiered-pr-review.md) | Tiered PR Review Architecture: Reference for Reviewers | Proposed | 2026-06-12 |
| [sonarcloud-nosonar-patterns](../sonarcloud-nosonar-patterns.md) | SonarCloud `# NOSONAR` Suppression Patterns | Living guide | 2026-05-25 |
