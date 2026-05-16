# Governance

## Status

ByronWilliamsCPA is currently a **sole-maintainer** organization. Byron
Williams (byronawilliams@gmail.com) is the sole maintainer and final
decision-maker for all repositories in the org that do not publish their own
governance document.

This is intentional. The org is small and the overhead of a formal
multi-role governance model is not justified yet. If the project grows
beyond what one maintainer can handle, this document will be updated to
reflect a fuller structure.

## Decision-Making

1. **Day-to-day changes** (bug fixes, dependency bumps, small features,
   documentation): the maintainer reviews and merges directly.
2. **Larger or breaking changes** (public API changes, new reusable
   workflows, removal of supported features): the maintainer opens an issue
   describing the change and waits at least seven calendar days from the
   issue creation date before merging, so external contributors and
   downstream consumers can comment.
3. **Security fixes**: reported via [SECURITY.md](SECURITY.md); the
   maintainer may merge fixes without the seven-day waiting period.

Decisions are final once merged. Disagreement is welcome before that point;
open an issue or comment on the PR.

## How to Propose a Change

1. Open an issue. If the repository provides issue templates, use the
   one that matches your change; otherwise open a plain issue. For
   non-trivial changes, describe the problem, the proposed solution,
   and any alternatives considered.
2. Wait for a maintainer response, or for the seven-day comment window
   on larger changes.
3. Submit a pull request that references the issue. Follow
   [CONTRIBUTING.md](CONTRIBUTING.md), including the GPG-signing
   requirement and PR checklist.

Proposals that would change governance itself (for example, adding new
roles or changing the decision process) should be opened as an issue
with `governance` in the title and discussed publicly before any PR is
filed.

## Succession

If the maintainer becomes unavailable, public repositories remain under the
existing license and can be forked by anyone. There is no formal succession
plan; if that changes, this section will be updated.

Last updated: May 15, 2026
