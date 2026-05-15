# python-mutation.yml -- Mutation Testing

Runs mutation testing with mutmut to evaluate test suite quality. Measures
what percentage of artificial code mutations are caught by the test suite.
This workflow can be long-running; schedule it weekly rather than on every push.

## Inputs

| Input | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `python-version` | string | no | `3.12` | Python version |
| `source-directory` | string | no | `src` | Source code directory to mutate |
| `test-directory` | string | no | `tests` | Test directory |
| `mutation-threshold` | number | no | `80` | Minimum mutation score percentage (0-100) |
| `fail-under-threshold` | boolean | no | `false` | Fail workflow if score is below threshold |
| `post-pr-comment` | boolean | no | `true` | Post mutation results as PR comment |
| `timeout-minutes` | number | no | `60` | Timeout for mutation testing |
| `artifact-retention-days` | number | no | `14` | Days to retain mutation reports |

## Usage

```yaml
jobs:
  mutation:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-mutation.yml@main
    with:
      mutation-threshold: 70
      fail-under-threshold: true
```
