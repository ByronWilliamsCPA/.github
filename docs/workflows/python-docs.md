# python-docs.yml -- Documentation Build and Deploy

Builds MkDocs documentation and optionally deploys to GitHub Pages.
Also checks docstring coverage using interrogate.

## Inputs

| Input | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `python-version` | string | no | `3.12` | Python version for MkDocs build |
| `docs-directory` | string | no | `docs` | Documentation source directory |
| `source-directory` | string | no | `src` | Source code directory for docstring extraction |
| `deploy-to-pages` | boolean | no | `false` | Deploy to GitHub Pages (main branch only) |
| `docstring-threshold` | number | no | `80` | Minimum docstring coverage percentage |

## Usage

```yaml
jobs:
  docs:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-docs.yml@v1
    with:
      deploy-to-pages: ${{ github.ref == 'refs/heads/main' }}
```
