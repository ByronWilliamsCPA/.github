# Python Version Policy

Single source of truth for the Python versions this org's reusable workflows and
templates target. GitHub Actions does not allow a `workflow_call` input `default:`
to reference a variable, so the versions cannot be injected from one place at
runtime. Instead this file is the canonical record and
`scripts/check-python-versions.sh` enforces it: the `self-test.yml` CI workflow
fails if any workflow or template drifts from the supported set below.

To change the supported versions, edit the two machine-readable markers here,
update the table, then update each workflow to match and run the checker.

<!-- python-versions:supported = 3.10 3.11 3.12 3.13 3.14 -->
<!-- python-versions:primary = 3.12 -->

## Policy

| Role | Versions | Notes |
|------|----------|-------|
| Primary | 3.12 | Default for single-version `python-version` inputs and the version quality checks run on |
| Supported matrix | 3.10, 3.11, 3.12, 3.13, 3.14 | Comprehensive test matrix |
| PR fast tier | 3.11, 3.12 | Subset for fast PR feedback; must be a subset of the supported matrix |

A version joins the supported set once it has a stable release, and not before.
Do not name a specific version as the pre-release example here: the previous
wording used 3.14 as its illustration and quietly became wrong the moment 3.14
shipped, which is how 3.14 stayed excluded for months after it qualified. State
the rule, let the marker above carry the facts.

Coverage and artifact handlers may reference a not-yet-supported version
defensively (gated on the artifact existing) as long as no test matrix or input
default actively selects it.

The supported set is a permit list, not a mandate. `check-python-versions.sh`
fails on a version *outside* the set, so adding a version only widens what
workflows may select; it does not add that version to any matrix or change any
default. Removing a version is the direction that carries risk, because it can
invalidate workflows and downstream `requires-python` floors that are already in
use.

## Enforcement

`scripts/check-python-versions.sh` scans `.github/workflows/*.yml` and
`workflow-templates/*.yml` and fails if any `python-version(s)` input default or
test matrix references a version outside the supported set. Run it locally with:

```bash
scripts/check-python-versions.sh
```
