# python-pr-validation.yml -- Reusable PR validation workflow (deprecated)

> **Deprecated.** This workflow will be removed in a future release. Migrate to
> `python-ci.yml`, which provides all of its code-quality checks plus dead-code
> detection and tested coverage. See `.github/workflows/python-pr-validation.yml`
> for the full migration guide.

## Migration

Replace a `python-pr-validation.yml` caller with `python-ci.yml`:

```yaml
jobs:
  ci:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-ci.yml@v1
    secrets: inherit
```

See [python-ci.md](python-ci.md) for usage.
