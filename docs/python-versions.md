# Python Version Policy

Single source of truth for the Python versions this org's reusable workflows and
templates target. GitHub Actions does not allow a `workflow_call` input `default:`
to reference a variable, so the versions cannot be injected from one place at
runtime. Instead this file is the canonical record and
`scripts/check-python-versions.sh` enforces it: the `self-test.yml` CI workflow
fails if any workflow or template drifts from the supported set below.

To change the supported versions, edit the two machine-readable markers here,
update the table, then update each workflow to match and run the checker.

<!-- python-versions:supported = 3.10 3.11 3.12 3.13 -->
<!-- python-versions:primary = 3.12 -->

## Policy

| Role | Versions | Notes |
|------|----------|-------|
| Primary | 3.12 | Default for single-version `python-version` inputs and the version quality checks run on |
| Supported matrix | 3.10, 3.11, 3.12, 3.13 | Comprehensive test matrix |
| PR fast tier | 3.11, 3.12 | Subset for fast PR feedback; must be a subset of the supported matrix |

Pre-release versions (for example 3.14) are not part of the supported set until
they reach a stable release. Coverage and artifact handlers may reference a
pre-release version defensively (gated on the artifact existing) as long as no
test matrix or input default actively selects it.

## Enforcement

`scripts/check-python-versions.sh` scans `.github/workflows/*.yml` and
`workflow-templates/*.yml` and fails if any `python-version(s)` input default or
test matrix references a version outside the supported set. Run it locally with:

```bash
scripts/check-python-versions.sh
```
