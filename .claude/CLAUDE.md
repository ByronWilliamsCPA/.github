# .github Repository -- Claude Code Instructions

> Scope: this file applies when Claude Code is working in the ByronWilliamsCPA/.github repo.

## Repository Purpose

This is the GitHub org-level community health file repo and reusable workflow library
for ByronWilliamsCPA. It contains:

- Community health files (SECURITY.md, CONTRIBUTING.md, CODE_OF_CONDUCT.md, etc.)
- Reusable GitHub Actions workflows (`.github/workflows/python-*.yml`)
- Org-level profile (`profile/README.md`)

There is no Python package, no test suite, and no build system in this repo.

## Model Selection

| Task | Model |
|------|-------|
| Workflow YAML editing, doc fixes | Sonnet 4.6 (default) |
| Architecture decisions, ADRs | Opus 4.7 |
| File scanning, grep, read-only | Haiku 4.5 |

## Response-Aware Development (RAD)

Tag assumptions with `#CRITICAL`, `#ASSUME`, `#EDGE`, and `#VERIFY` in comments
when editing workflow YAML. Mandatory for: permission scopes, secret references,
OIDC token behavior, and reusable workflow caller/callee permission inheritance.

See: [docs/response-aware-development.md](https://github.com/ByronWilliamsCPA/.github/blob/main/docs/response-aware-development.md)

## Writing Rules

Never use em-dashes in any output (documentation, YAML run steps, commit messages).
Replace with comma, semicolon, or colon.

## Git Workflow

Branch naming: `claude/<description>-<id>` (e.g., `claude/compliance-quick-wins-0`).
Always run `pre-commit run --all-files` before committing.
Create worktrees at `.worktrees/<branch-slug>`.

## Cross-References

- Agents: [AGENTS.md](../AGENTS.md)
- Known vulnerabilities: [docs/known-vulnerabilities.md](../docs/known-vulnerabilities.md)
- Architecture decisions: [docs/architecture/adr-000-index.md](../docs/architecture/adr-000-index.md)
