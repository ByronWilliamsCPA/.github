# Reusable Workflows Documentation

This directory contains documentation for the organization's reusable GitHub Actions workflows.

## Available Workflows

### Python Workflows

| Workflow | Purpose | Documentation |
|----------|---------|---------------|
| **python-publish-pypi.yml** | Publish Python packages to PyPI/TestPyPI using OIDC | [Migration Guide](../migration/pypi-publishing-migration.md) |
| **python-fips-compatibility.yml** | Validate FIPS 140-2 compatibility | [FIPS Guide](python-fips-compatibility.md) |
| **python-ci.yml** | Python CI pipeline | *Coming soon* |
| **python-release.yml** | Automated semantic releases | *Coming soon* |
| **python-security-analysis.yml** | Security scanning suite | *Coming soon* |

## Quick Start

### Using Reusable Workflows

All reusable workflows follow this pattern:

```yaml
# In your repository's .github/workflows/my-workflow.yml
name: My Workflow

on:
  push:
    branches: [main]

jobs:
  my-job:
    uses: ByronWilliamsCPA/.github/.github/workflows/WORKFLOW-NAME.yml@main
    with:
      # Workflow-specific inputs
      input-name: 'value'
    permissions:
      # Workflow-specific permissions
      contents: read
```

### PyPI Publishing Example

```yaml
name: Publish to PyPI

on:
  release:
    types: [published]

jobs:
  publish:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-publish-pypi.yml@main
    with:
      package-name: 'my-package'
    permissions:
      id-token: write
      contents: read
```

See [examples/publish-pypi-caller.yml](../../examples/publish-pypi-caller.yml) for a complete example.

## Migration Guides

- [PyPI Publishing Migration](../migration/pypi-publishing-migration.md) - Convert standalone PyPI workflows to reusable workflow

## Benefits of Reusable Workflows

1. **Centralized Maintenance** - Update once, all repositories benefit
2. **Consistency** - Same behavior across all projects
3. **Security** - Built-in security scanning and best practices
4. **Reduced Boilerplate** - Less code in each repository
5. **Version Pinning** - Use `@main` for latest or pin to specific tags

## Workflow Development

### Creating New Reusable Workflows

1. **Create workflow** in `.github/workflows/` with `workflow_call` trigger
2. **Define inputs** using `inputs:` section
3. **Document usage** in this directory
4. **Create example** in `examples/` directory
5. **Test thoroughly** before promoting to `@main`

### Workflow Naming Convention

| Pattern | Example | Purpose |
|---------|---------|---------|
| `python-*.yml` | `python-ci.yml` | Python-specific workflows |
| `nodejs-*.yml` | `nodejs-test.yml` | Node.js-specific workflows |
| `docker-*.yml` | `docker-build.yml` | Docker/container workflows |
| `general-*.yml` | `general-security.yml` | Language-agnostic workflows |

### Best Practices

1. **Use semantic versioning tags** - Tag stable releases with `v1.0.0`
2. **Provide defaults** - All inputs should have sensible defaults
3. **Document inputs** - Clear descriptions for all parameters
4. **Security first** - Include security scanning by default
5. **Fail fast** - Validate inputs early in the workflow
6. **Clear outputs** - Use `GITHUB_STEP_SUMMARY` for results

## Support

For questions or issues:
1. Check workflow-specific documentation
2. Review examples in `examples/` directory
3. Open an issue in the `.github` repository

## Additional Resources

- [GitHub Actions: Reusing Workflows](https://docs.github.com/en/actions/using-workflows/reusing-workflows)
- [GitHub Actions: Security Hardening](https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions)
- [OpenSSF Scorecard](https://securityscorecards.dev/)
