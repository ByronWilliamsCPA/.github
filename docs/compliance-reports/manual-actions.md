# Manual Compliance Actions

Items that require external action, conflict with solo_dev_constraints, or self-correct with time.
Do not auto-remediate these. Review quarterly.

## OSSF-001: Best Practices Badge

**Status:** Pending manual filing
**Action:** File at https://bestpractices.coreinfrastructure.org/en/projects/new
**Blocker:** Requires web form submission. After filing, add the badge URL to README.md.
**Review by:** 2026-08-14

## SCORECARD:Code-Review

**Status:** Accepted score impact
**Reason:** solo_dev_constraints forbids required_approving_review_count > 0. Requiring
a reviewer would block all merges for a solo maintainer. This is a known trade-off.
**Check ID:** No manifest entry (Scorecard native check)
**Review by:** Reassess if team grows beyond 1 maintainer.

## SCORECARD:Branch-Protection (approver component)

**Status:** Accepted score impact
**Reason:** Same constraint as SCORECARD:Code-Review. Org rulesets (IDs 16183607, 16183609)
provide structural branch protection without required reviewers.
**Review by:** Reassess if team grows beyond 1 maintainer.

## SCORECARD:Maintained

**Status:** Will self-correct
**Reason:** Score is 0 because the repo is under 90 days old as of 2026-05-14.
Scorecard requires at least one commit in the last 90 days evaluated over a 1-year window.
**Expected resolution:** 2026-08-13 (90 days from repo creation)
**Review by:** Re-audit after 2026-08-14.
