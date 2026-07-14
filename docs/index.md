# ByronWilliamsCPA `.github`

Centralized community health files and reusable GitHub Actions workflows for
the `ByronWilliamsCPA` GitHub organization. This repository serves two
purposes:

- **Community health files** (`CODE_OF_CONDUCT.md`, `SECURITY.md`,
  `CONTRIBUTING.md`, `SUPPORT.md`, `GOVERNANCE.md`, issue and PR templates)
  that GitHub automatically surfaces on every public repository in the
  organization that doesn't define its own copy.
- **A reusable workflow library** (`.github/workflows/python-*.yml` and
  `supply-chain-*.yml`) that calling repositories reference via
  `uses: ByronWilliamsCPA/.github/.github/workflows/<name>.yml@<sha>` to get
  standardized CI, security scanning, SBOM generation, release automation,
  and supply-chain verification without duplicating pipeline logic.

There is no Python package or build system in this repository itself; it is
a documentation and workflow-template repo, and the reusable workflows exist
to serve *other* Python repositories in the org.

## Where to start

- **[Workflows](workflows/README.md)** - per-workflow reference docs for
  every reusable GitHub Actions workflow this repo publishes, organized by
  Python CI/security workflows and supply-chain verification workflows.
- **[Architecture](architecture/adr-000-index.md)** - architecture decision
  records (ADRs), the CI pipeline overview, the tiered PR-review model, and
  relationship diagrams between the reusable workflows.
- **[Integrations](integrations/qlty-cloud.md)** - setup notes for external
  platforms (Qlty Cloud, SonarCloud, Snyk) that some workflows depend on.
- **[Compliance](compliance/README.md)** - point-in-time audit reports,
  tracked remediation issues, and manual compliance actions.

## Other sections

- **[Migration](migration/image-detection-pypi-migration.md)** - guides for
  one-time migrations (PyPI publishing, image-detection pipeline changes).
- **[Planning](planning/roadmap.md)** - the current project plan and
  roadmap.
- **[Reference](known-vulnerabilities.md)** - standing reference pages:
  known vulnerabilities, the supported Python versions policy, and
  SonarCloud NOSONAR usage patterns.
- **[Archive](archive/README.md)** - superseded planning snapshots and
  completed handoffs, kept for provenance only.

## Repository root files

The canonical, always-current index of every reusable workflow with a
one-line description lives in the repository
[README](https://github.com/ByronWilliamsCPA/.github#available-workflows).
The docs under [Workflows](workflows/README.md) go deeper on individual
workflows; the README stays the fastest place to scan the full list.
