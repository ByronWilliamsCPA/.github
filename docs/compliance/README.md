# Compliance

Audit records, tracked follow-up issues, measurement baselines, and manual
compliance actions for this repository. `docs/known-vulnerabilities.md`
stays at the repo `docs/` root (not here) because it is referenced by fixed
path from both the global and project `CLAUDE.md` files.

## Structure

- [`audits/`](audits/) - point-in-time audit reports. Each is a snapshot;
  read them as history, not current state.
  - [`2026-04-18-standards-audit.md`](audits/2026-04-18-standards-audit.md)
  - [`2026-05-01-security-audit.md`](audits/2026-05-01-security-audit.md)
  - [`2026-05-29/`](audits/2026-05-29/) - full six-domain audit (dependencies,
    code quality, architecture, security, CI/CD, docs) plus a final report
    and machine-readable findings.
- [`issues/`](issues/) - handoffs for individual findings, tracked until
  resolved.
  - [`2026-05-26-issue-168-merge-group-security-handoff.md`](issues/2026-05-26-issue-168-merge-group-security-handoff.md) - resolved, kept for history.
  - [`2026-06-10-python-release-no-build-handoff.md`](issues/2026-06-10-python-release-no-build-handoff.md) - still open; see the flagged
    follow-up on `python-release`'s `no-build` default.
- [`baselines/`](baselines/) - point-in-time measurement snapshots for
  tracking drift over time.
  - [`2026-05-25-sha-pin-sweep-baseline.csv`](baselines/2026-05-25-sha-pin-sweep-baseline.csv)
- [`manual-actions.md`](manual-actions.md) - items requiring external action,
  conflicting with solo-dev constraints, or expected to self-correct with
  time. Reviewed quarterly.
