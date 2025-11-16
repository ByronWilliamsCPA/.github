# Security Policy

## Reporting a Vulnerability  

If you discover a security vulnerability in any project under our organization,
**please do not open a public issue**.
Instead, use GitHub’s built-in Security advisories feature:  

1. Go to the repository’s **Security** tab
2. Click **“Report a vulnerability”**  
3. Fill in the details and submit  

All reports will be kept confidential. We commit to acknowledging receipt and
next steps via the Security tab.

## Supported Versions  

The following table shows which major releases we support. For full upgrade
paths and end-of-life schedules, see our [Upgrade Guide][upgrade‐guide].

| Version  | Status       |
|----------|--------------|
| v3.x     | Supported    |
| v2.x     | Security‐only support |
| v1.x     | End of life  |

## Security Practices  

We strive for proactive, comprehensive security across our codebases and infrastructure.
Our standard practices include:  

- **Static Analysis** with CodeQL, Semgrep, Ruff, and Bandit  
- **Dependency Pinning** for reproducible builds  
- **Container Scanning** using Trivy  
- **SBOM Generation** for each release  
- **Secrets Detection** integrated in CI pipelines  
- **Hardened CI Runners** with minimal privileges  

## CVE & Advisory Workflow  

We track and publish advisories for all confirmed vulnerabilities:

1. **Request a CVE** for issues rated Moderate or above.  
2. **Draft and publish an advisory** in the Security tab.  
3. **Include remediation steps** in release notes and upgrade guide.  

## Response Timeline  

- **Acknowledgment:** within 5 business days  
- **Fix released:** within 30 days of acknowledgment  
- **Emergency patch:** sooner for critical severity  

## Disclosure Policy  

We follow coordinated disclosure principles. Once a fix is available, we will
publish details in our Security Advisories page. If you wish to receive credit
for responsibly disclosing a vulnerability, please let us know; otherwise
credit will be anonymous.

## Credit  

This policy is based on community best practices and has drawn on elements from
multiple sources within our organization’s previous drafts.

_Last updated: November 16, 2025_  

[upgrade‐guide]: https://github.com/williaby/.github/blob/main/UPGRADE_GUIDE.md  
