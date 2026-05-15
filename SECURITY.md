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

This repository is a community health and reusable workflow library. Releases
are continuous on `main`; there are no long-term branches.

| Version          | Supported          |
|------------------|--------------------|
| `main` (latest)  | Yes                |
| Tagged releases  | Yes, latest minor  |
| Pinned commit SHAs older than the latest minor release | No |

If you pin a workflow to a specific commit SHA, you must bump the pin to pick
up security fixes. Older SHAs do not receive backports.

## Response Timeline

| Stage                          | Target                  |
|--------------------------------|-------------------------|
| Acknowledgement of report      | 5 business days         |
| Initial triage and severity    | 10 business days        |
| Fix or mitigation for critical | 14 calendar days        |
| Fix released (other severities)| 30 calendar days        |

These are targets, not guarantees. The maintainer will keep the reporter
updated if a fix needs longer.

## Security Practices

The org applies the following baseline across its repositories:

- Static analysis with CodeQL, Semgrep, Ruff, and Bandit
- Dependency pinning and Renovate-driven updates
- Container scanning with Trivy
- SBOM generation for tagged releases
- Secret scanning in CI (gitleaks, TruffleHog, detect-secrets)
- Least-privilege workflow tokens and pinned action SHAs

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
