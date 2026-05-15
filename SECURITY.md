# Security Policy

## Reporting a Vulnerability

Do not open a public issue for security problems. Use one of these private
channels:

1. **GitHub Security Advisory** (preferred): go to the affected repository's
   **Security** tab and click **Report a vulnerability**.
2. **Email**: send details to **byronawilliams@gmail.com**. Use the subject
   line `SECURITY:` followed by a short summary.

Both channels are monitored by the maintainer. Reports remain confidential
until a fix is published.

## What to Include in a Report

A useful report contains, at minimum:

- A clear description of the issue and the security impact (what an attacker
  can do).
- The affected repository, file path, workflow, or commit SHA.
- Steps to reproduce, including any inputs, environment, or configuration
  needed.
- A proof of concept if you have one (snippet, log, or test case).
- Suggested fix or mitigation, if known.
- Your contact details and whether you want public credit in the advisory.

If the issue affects a downstream repository that consumes a reusable workflow
from this org, please name the consumer repo as well.

## Supported Versions

This repository is a community health and reusable workflow library with
continuous deployment on `main`. The `CHANGELOG.md` uses date-based section
headers (for example, `[2025-01-07]`). Release tags follow semver; there are
no long-term support branches.

| Version                                               | Supported |
|-------------------------------------------------------|-----------|
| `main` (latest commit)                                | Yes       |
| Most recent release tag                               | Yes       |
| Earlier release tags and older pinned SHAs            | No        |

If you pin a workflow to a specific commit SHA, bump the pin to pick up
security fixes. Older SHAs do not receive backports.

## Response Timeline

| Stage                                  | Target                  |
|----------------------------------------|-------------------------|
| Acknowledgement of report              | 5 business days         |
| Triage and severity (non-critical)     | 10 business days        |
| Triage and severity (critical)         | 2 business days         |
| Fix or mitigation for critical reports | 14 calendar days from acknowledgement |
| Fix released for other severities      | 30 calendar days from acknowledgement |

These are targets, not guarantees. The fix windows run from triage
completion, not from the initial report date. The maintainer will keep the
reporter updated if a fix needs longer.

## Security Practices

The org applies the following baseline across its repositories. Not every
tool runs in every repo; the list reflects what is wired up in this
repository's workflows and pre-commit hooks, which downstream repos
inherit via the reusable workflows.

- Static analysis: CodeQL (org-wide), SonarCloud (incorporates Semgrep rule
  patterns), Ruff and Bandit (Python reusable workflows)
- Dependency pinning and Renovate-driven updates
- Container scanning with Trivy (Docker and SBOM workflows)
- SBOM generation for tagged releases
- Secret scanning: `detect-secrets` and TruffleHog as `pre-commit` hooks,
  GitHub secret scanning (enabled by default on public repositories)
- Least-privilege workflow tokens and SHA-pinned third-party actions

## CVE and Advisory Workflow

For confirmed vulnerabilities rated Moderate or higher:

1. Request a CVE through GitHub.
2. Draft and publish a GitHub Security Advisory on the affected repository.
3. Record remediation in the advisory and in the repository's CHANGELOG.

## Disclosure

The org follows coordinated disclosure. Public details are published in the
advisory once a fix or mitigation is available. Reporters who want credit
should say so in the report; otherwise credit is anonymous.

Last updated: May 15, 2026
