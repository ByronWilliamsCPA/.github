# python-performance-regression.yml -- Performance Regression Detection

Benchmarks key code paths and fails if performance regresses beyond a
configurable threshold. Requires a caller-supplied benchmark script that
outputs JSON with performance metrics.

## Inputs

| Input | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `benchmark-script` | string | **yes** | | Path to benchmark script (must output JSON with metrics) |
| `primary-metric` | string | no | `p95_ms` | Primary metric to track (e.g., `p95_ms`, `throughput`) |
| `regression-threshold` | number | no | `10.0` | Maximum allowed regression percentage |
| `improvement-threshold` | number | no | `5.0` | Minimum improvement percentage to highlight |
| `python-version` | string | no | `3.12` | Python version for benchmarking |
| `warmup-iterations` | number | no | `10` | Warmup iterations before measurement |
| `benchmark-iterations` | number | no | `100` | Benchmark iterations for measurement |
| `fail-on-regression` | boolean | no | `true` | Fail workflow if regression detected |
| `comment-on-pr` | boolean | no | `true` | Post performance results as PR comment |

## Benchmark script contract

The `benchmark-script` must write a JSON object to stdout with at least one
numeric metric key matching the `primary-metric` input. Example:

```json
{"p95_ms": 45.2, "p99_ms": 52.1, "throughput": 1200}
```

## Usage

```yaml
jobs:
  perf:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-performance-regression.yml@main
    with:
      benchmark-script: scripts/benchmark.py
      regression-threshold: 15
```
