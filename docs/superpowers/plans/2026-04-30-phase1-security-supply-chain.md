# Phase 1: Security Fixes and Supply Chain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate all critical and high security findings from the 23 org-level reusable workflows -- no `${{ inputs.* }}` unquoted in any `run:` block, no Python heredoc injection, and supply chain defaults hardened.

**Architecture:** Two parallel worktrees merge into the integration branch before the PR opens. Worktree A handles the single CRIT file (`python-performance-regression.yml`). Worktree B handles the systematic env-var sweep across nine other files plus supply chain fixes. Both worktrees live at `.worktrees/<branch-slug>` inside the project root per `.claude/rules/git-workflow.md`. All changes are YAML edits only -- no application code exists in this repo.

**Tech Stack:** GitHub Actions YAML, qlty (actionlint + shellcheck validation), pre-commit

---

## File Structure

**Modified in Worktree A** (`fix/perf-regression-rce`):
- `.github/workflows/python-performance-regression.yml` (541 lines): remove `synthetic-data-script` input, move heredoc inputs to env vars, move benchmark inputs to env vars

**Modified in Worktree B** (`fix/workflow-input-quoting`):
- `.github/workflows/python-ci.yml` (716 lines): env-var pattern for string inputs, permission scoping, exit-code-5 fix
- `.github/workflows/python-compatibility.yml` (294 lines): env-var pattern, package name validation
- `.github/workflows/python-docs.yml` (145 lines): permission scoping, remove redundant cache, add harden-runner to deploy job
- `.github/workflows/python-release.yml` (332 lines): permission scoping, `if: always()` on artifact upload
- `.github/workflows/python-security-analysis.yml` (420 lines): move boolean heredoc inputs to env vars
- `.github/workflows/python-pr-validation.yml` (546 lines): env-var pattern for string inputs in run: blocks
- `.github/workflows/python-slsa.yml` (100 lines): SHA-pin comment examples, add SLSA-not-included header note
- `.github/workflows/python-publish-pypi.yml` (228 lines): replace unpinned safety block with pip-audit + bandit
- `.github/workflows/python-docker.yml` (399 lines): flip `enable-sbom` default to `true`, add `enable-provenance` input

---

## Task 0: Create Branches and Worktrees

**Files:** none (branch and worktree setup)

- [ ] **Step 1: Create the integration branch**

```bash
cd /home/byron/dev/.github
git checkout main
git checkout -b fix/workflow-security-remediation
git push -u origin fix/workflow-security-remediation
git checkout main
```

- [ ] **Step 2: Create Worktree A**

```bash
git checkout -b fix/perf-regression-rce
git worktree add .worktrees/fix-perf-regression-rce fix/perf-regression-rce
git checkout main
```

- [ ] **Step 3: Create Worktree B**

```bash
git checkout -b fix/workflow-input-quoting
git worktree add .worktrees/fix-workflow-input-quoting fix/workflow-input-quoting
```

- [ ] **Step 4: Verify worktrees**

```bash
git worktree list
```

Expected output (three entries):
```
/home/byron/dev/.github                     <sha> [main]
/home/byron/dev/.github/.worktrees/fix-perf-regression-rce    <sha> [fix/perf-regression-rce]
/home/byron/dev/.github/.worktrees/fix-workflow-input-quoting  <sha> [fix/workflow-input-quoting]
```

---

## WORKTREE A TASKS
### Work directory: `.worktrees/fix-perf-regression-rce`
### All commands in this section run from `.worktrees/fix-perf-regression-rce`

---

## Task 1 (Worktree A): CRIT-01 -- Remove `synthetic-data-script` Input

**Files:**
- Modify: `.github/workflows/python-performance-regression.yml:110-192`

- [ ] **Step 1: Confirm the target code**

```bash
grep -n "synthetic-data-script\|synthetic_data_script\|generate-synthetic-data" \
  .github/workflows/python-performance-regression.yml
```

Expected: hits on lines 110-120 (input definition) and lines 184-192 (usage step).

- [ ] **Step 2: Remove the `synthetic-data-script` input definition (lines 116-120)**

In `.github/workflows/python-performance-regression.yml`, delete these five lines:

```yaml
      synthetic-data-script:
        description: 'Python code to generate synthetic test data'
        type: string
        required: false
        default: ''
```

- [ ] **Step 3: Replace the Generate Synthetic Test Data step (lines 184-192)**

Replace:

```yaml
      - name: Generate Synthetic Test Data
        if: inputs.generate-synthetic-data && inputs.synthetic-data-script != ''
        run: |
          mkdir -p "${{ inputs.test-data-directory }}"
          uv run python - <<'EOF'
          ${{ inputs.synthetic-data-script }}
          EOF
          echo "✅ Synthetic test data generated in ${{ inputs.test-data-directory }}"
          ls -lh "${{ inputs.test-data-directory }}" | head -20
```

With:

```yaml
      - name: Generate Synthetic Test Data
        if: inputs.generate-synthetic-data
        env:
          TEST_DATA_DIR: ${{ inputs.test-data-directory }}
        run: |
          mkdir -p "$TEST_DATA_DIR"
          uv run python scripts/generate_test_data.py
          echo "Synthetic test data generated in $TEST_DATA_DIR"
          ls -lh "$TEST_DATA_DIR" | head -20
```

Add this comment to the workflow header (inside the existing `# ===` block at the top of the file, after the Features section):

```yaml
# Caller convention: place data-generation script at scripts/generate_test_data.py
# in the calling repository. The script is invoked when generate-synthetic-data: true.
```

- [ ] **Step 4: Validate**

```bash
qlty check --plugin actionlint --plugin shellcheck \
  .github/workflows/python-performance-regression.yml
```

Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/python-performance-regression.yml
git commit -m "fix(security): remove synthetic-data-script RCE vector (CRIT-01)

Replace arbitrary Python execution heredoc with fixed-path convention.
Callers place their script at scripts/generate_test_data.py."
```

---

## Task 2 (Worktree A): CRIT-02 -- Move Heredoc Inputs to Env Vars

**Files:**
- Modify: `.github/workflows/python-performance-regression.yml:337-423`

The `Compare Performance` step (lines 335-423) interpolates four inputs directly into Python syntax inside a heredoc. This allows callers to inject arbitrary Python expressions.

- [ ] **Step 1: Confirm injection points**

```bash
grep -n "\${{ inputs\." .github/workflows/python-performance-regression.yml | grep -v "^[0-9]*:#"
```

Expected hits inside the heredoc (around lines 348, 353, 354, 419):
- `primary_metric = "${{ inputs.primary-metric }}"`
- `regression_threshold = ${{ inputs.regression-threshold }}`
- `improvement_threshold = ${{ inputs.improvement-threshold }}`
- `if regression_detected and ${{ inputs.fail-on-regression }}:`

- [ ] **Step 2: Add `env:` block to the Compare Performance step and update Python code**

Find the `- name: Compare Performance` step (line ~334). Replace the `run:` key and its content with:

```yaml
      - name: Compare Performance
        id: compare
        env:
          PRIMARY_METRIC: ${{ inputs.primary-metric }}
          REGRESSION_THRESHOLD: ${{ inputs.regression-threshold }}
          IMPROVEMENT_THRESHOLD: ${{ inputs.improvement-threshold }}
          FAIL_ON_REGRESSION: ${{ inputs.fail-on-regression }}
        run: |
          uv run python - <<'EOF'
          import json
          import os
          import sys
          from pathlib import Path

          # Load results
          pr_results = json.loads(Path("/tmp/pr_benchmark.json").read_text())
          baseline_results = json.loads(Path("/tmp/baseline_benchmark.json").read_text())

          # Extract primary metric
          primary_metric = os.environ["PRIMARY_METRIC"]
          pr_value = pr_results.get(primary_metric, 0.0)
          baseline_value = baseline_results.get(primary_metric, 0.0)

          # Get thresholds from inputs
          regression_threshold = float(os.environ["REGRESSION_THRESHOLD"])
          improvement_threshold = float(os.environ["IMPROVEMENT_THRESHOLD"])

          # Handle missing or zero values
          if baseline_value == 0:
              print(f"WARNING: Baseline {primary_metric} is 0 - cannot calculate regression")
              regression_pct = 0
              regression_detected = False
              improvement_detected = False
          else:
              regression_pct = ((pr_value - baseline_value) / baseline_value) * 100
              regression_detected = regression_pct > regression_threshold
              improvement_detected = regression_pct < -improvement_threshold

          # Print results
          print(f"Performance Comparison:")
          print(f"  Metric: {primary_metric}")
          print(f"  Baseline: {baseline_value:.2f}")
          print(f"  PR: {pr_value:.2f}")
          print(f"  Change: {regression_pct:+.1f}%")
          print(f"  Threshold: +/-{regression_threshold}%")
          print()

          if regression_detected:
              print(f"REGRESSION DETECTED ({regression_pct:+.1f}%)")
              status = "regression"
          elif improvement_detected:
              print(f"IMPROVEMENT DETECTED ({regression_pct:+.1f}%)")
              status = "improvement"
          else:
              print(f"PERFORMANCE OK ({regression_pct:+.1f}%)")
              status = "ok"

          # Extract additional metrics for summary
          summary_metrics = {}
          for key in pr_results.keys():
              if key != "status" and key in baseline_results:
                  pr_val = pr_results[key]
                  base_val = baseline_results[key]
                  if base_val != 0:
                      change_pct = ((pr_val - base_val) / base_val) * 100
                      summary_metrics[key] = {
                          "baseline": base_val,
                          "pr": pr_val,
                          "change_pct": change_pct
                      }

          # Write to GitHub output
          github_output = os.getenv("GITHUB_OUTPUT", "/tmp/github_output.txt")
          with open(github_output, "a") as f:
              f.write(f"baseline_value={baseline_value:.2f}\n")
              f.write(f"pr_value={pr_value:.2f}\n")
              f.write(f"regression_pct={regression_pct:+.1f}\n")
              f.write(f"regression_detected={str(regression_detected).lower()}\n")
              f.write(f"improvement_detected={str(improvement_detected).lower()}\n")
              f.write(f"status={status}\n")
              f.write(f"primary_metric={primary_metric}\n")
              import json as json2
              f.write(f"summary_metrics={json2.dumps(summary_metrics)}\n")

          # Exit with error if regression detected and fail-on-regression is true
          fail_on_regression = os.environ.get("FAIL_ON_REGRESSION", "false").lower() == "true"
          if regression_detected and fail_on_regression:
              sys.exit(1)
          else:
              sys.exit(0)
          EOF
```

- [ ] **Step 3: Validate**

```bash
qlty check --plugin actionlint --plugin shellcheck \
  .github/workflows/python-performance-regression.yml
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/python-performance-regression.yml
git commit -m "fix(security): move heredoc inputs to env vars (CRIT-02)

All inputs previously interpolated as raw Python syntax now read via
os.environ inside the Compare Performance heredoc."
```

---

## Task 3 (Worktree A): HIGH-05 -- Move Benchmark Shell Inputs to Env Vars

**Files:**
- Modify: `.github/workflows/python-performance-regression.yml:194-310`

The benchmark-script, benchmark-args, warmup-iterations, and benchmark-iterations inputs are interpolated directly into shell commands without quoting.

- [ ] **Step 1: Confirm injection points**

```bash
grep -n "inputs\.benchmark-\|inputs\.warmup\|inputs\.benchmark-args" \
  .github/workflows/python-performance-regression.yml
```

Expected hits at lines ~196, 212, 219, 227-231, 300-302 (Validate Benchmark Script and Run PR/Baseline Benchmarks steps).

- [ ] **Step 2: Apply env-var pattern to the Validate Benchmark Script step**

Find the `Validate Benchmark Script` step (line ~194). Replace with:

```yaml
      - name: Validate Benchmark Script
        env:
          BENCHMARK_SCRIPT: ${{ inputs.benchmark-script }}
          PRIMARY_METRIC: ${{ inputs.primary-metric }}
        run: |
          if [ ! -f "$BENCHMARK_SCRIPT" ]; then
            echo "ERROR: Benchmark script not found: $BENCHMARK_SCRIPT"
            echo ""
            echo "Ensure the script exists and outputs JSON with metrics:"
            echo "  {\"$PRIMARY_METRIC\": 100.0, \"mean_ms\": 95.0, ...}"
            exit 1
          fi
          echo "Benchmark script found: $BENCHMARK_SCRIPT"
```

- [ ] **Step 3: Apply env-var pattern to the Run PR Benchmarks step**

Find the `Run PR Benchmarks` step (line ~205). Replace with:

```yaml
      - name: Run PR Benchmarks
        id: pr_bench
        env:
          BENCHMARK_SCRIPT: ${{ inputs.benchmark-script }}
          BENCHMARK_ARGS: ${{ inputs.benchmark-args }}
          WARMUP_ITERATIONS: ${{ inputs.warmup-iterations }}
          BENCHMARK_ITERATIONS: ${{ inputs.benchmark-iterations }}
          PRIMARY_METRIC: ${{ inputs.primary-metric }}
        run: |
          echo "Running benchmark on PR branch..."

          SUPPORTS_OUTPUT=false
          if uv run python "$BENCHMARK_SCRIPT" --help 2>&1 | grep -q -- '--output'; then
            SUPPORTS_OUTPUT=true
          fi

          SUPPORTS_ITERATIONS=false
          if uv run python "$BENCHMARK_SCRIPT" --help 2>&1 | grep -q -- '--iterations'; then
            SUPPORTS_ITERATIONS=true
          fi

          if [ "$SUPPORTS_OUTPUT" = "true" ] && [ "$SUPPORTS_ITERATIONS" = "true" ]; then
            uv run python "$BENCHMARK_SCRIPT" \
              --warmup "$WARMUP_ITERATIONS" \
              --iterations "$BENCHMARK_ITERATIONS" \
              --output /tmp/pr_benchmark.json \
              $BENCHMARK_ARGS || {
                echo "Benchmark execution failed, creating fallback results"
                echo "{\"$PRIMARY_METRIC\": 0, \"status\": \"failed\"}" > /tmp/pr_benchmark.json
              }
          elif [ "$SUPPORTS_OUTPUT" = "true" ]; then
            uv run python "$BENCHMARK_SCRIPT" \
              --output /tmp/pr_benchmark.json \
              $BENCHMARK_ARGS || {
                echo "Benchmark execution failed, creating fallback results"
                echo "{\"$PRIMARY_METRIC\": 0, \"status\": \"failed\"}" > /tmp/pr_benchmark.json
              }
          else
            uv run python "$BENCHMARK_SCRIPT" $BENCHMARK_ARGS > /tmp/pr_benchmark.json || {
              echo "Benchmark execution failed, creating fallback results"
              echo "{\"$PRIMARY_METRIC\": 0, \"status\": \"failed\"}" > /tmp/pr_benchmark.json
            }
          fi
```

- [ ] **Step 4: Apply the same env-var pattern to the Run Baseline Benchmarks step**

Find `Run Baseline Benchmarks` (line ~295). Apply the identical env: block and replace all `${{ inputs.benchmark-script }}`, `${{ inputs.benchmark-args }}`, `${{ inputs.warmup-iterations }}`, `${{ inputs.benchmark-iterations }}`, `${{ inputs.primary-metric }}` with `$BENCHMARK_SCRIPT`, `$BENCHMARK_ARGS`, `$WARMUP_ITERATIONS`, `$BENCHMARK_ITERATIONS`, `$PRIMARY_METRIC` respectively, following the same pattern as Step 3.

- [ ] **Step 5: Validate**

```bash
qlty check --plugin actionlint --plugin shellcheck \
  .github/workflows/python-performance-regression.yml
pre-commit run --all-files
```

Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/python-performance-regression.yml
git commit -m "fix(security): move benchmark inputs to env vars (HIGH-05)

benchmark-script, benchmark-args, warmup-iterations, benchmark-iterations
now declared in env: blocks and referenced as quoted shell variables."
```

---

## WORKTREE B TASKS
### Work directory: `.worktrees/fix-workflow-input-quoting`
### All commands in this section run from `.worktrees/fix-workflow-input-quoting`

---

## Task 4 (Worktree B): `python-ci.yml` -- Permission Scoping and Exit-Code-5 Fix

**Files:**
- Modify: `.github/workflows/python-ci.yml:131-134, 196-238, 290-318`

- [ ] **Step 1: Remove workflow-level over-scoped permissions (lines 131-134)**

Find and replace:

```yaml
permissions:
  contents: read
  pull-requests: write
  checks: write
```

With:

```yaml
permissions:
  contents: read
```

- [ ] **Step 2: Apply env-var pattern to Set up Python step (line 197)**

Find:

```yaml
      - name: Set up Python
        run: uv python install ${{ inputs.python-version }}
```

Replace with:

```yaml
      - name: Set up Python
        env:
          PYTHON_VERSION: ${{ inputs.python-version }}
        run: uv python install "$PYTHON_VERSION"
```

- [ ] **Step 3: Apply env-var pattern to Run Ruff formatter check step (line 205)**

Find:

```yaml
      - name: Run Ruff formatter check
        run: |
          echo "::group::Ruff Formatting"
          uv run ruff format --check ${{ inputs.source-directory }}/ ${{ inputs.test-directory }}/ || {
            echo "::error::Code formatting issues detected. Run 'uv run ruff format ${{ inputs.source-directory }}/ ${{ inputs.test-directory }}/' to fix."
            exit 1
          }
          echo "::endgroup::"
```

Replace with:

```yaml
      - name: Run Ruff formatter check
        env:
          SRC_DIR: ${{ inputs.source-directory }}
          TEST_DIR: ${{ inputs.test-directory }}
        run: |
          echo "::group::Ruff Formatting"
          uv run ruff format --check "$SRC_DIR/" "$TEST_DIR/" || {
            echo "::error::Code formatting issues detected. Run 'uv run ruff format $SRC_DIR/ $TEST_DIR/' to fix."
            exit 1
          }
          echo "::endgroup::"
```

- [ ] **Step 4: Apply env-var pattern to Run Ruff linter step (line 212)**

Find:

```yaml
      - name: Run Ruff linter
        run: |
          echo "::group::Ruff Linting"
          uv run ruff check ${{ inputs.source-directory }}/ ${{ inputs.test-directory }}/ --output-format=github
          echo "::endgroup::"
```

Replace with:

```yaml
      - name: Run Ruff linter
        env:
          SRC_DIR: ${{ inputs.source-directory }}
          TEST_DIR: ${{ inputs.test-directory }}
        run: |
          echo "::group::Ruff Linting"
          uv run ruff check "$SRC_DIR/" "$TEST_DIR/" --output-format=github
          echo "::endgroup::"
```

- [ ] **Step 5: Apply env-var pattern to Run BasedPyright type checker step (line 218)**

Find:

```yaml
      - name: Run BasedPyright type checker
        run: |
          echo "::group::BasedPyright Type Checking"
          uv run basedpyright ${{ inputs.source-directory }}/ || {
            echo "::warning::Type checking found issues"
          }
          echo "::endgroup::"
```

Replace with:

```yaml
      - name: Run BasedPyright type checker
        env:
          SRC_DIR: ${{ inputs.source-directory }}
        run: |
          echo "::group::BasedPyright Type Checking"
          uv run basedpyright "$SRC_DIR/" || {
            echo "::warning::Type checking found issues"
          }
          echo "::endgroup::"
```

- [ ] **Step 6: Apply env-var pattern to Dead code detection with Vulture step (line 226)**

Find the `Dead code detection with Vulture` step and replace the lines that interpolate inputs:

```yaml
          echo "Scanning for dead code (min confidence: ${{ inputs.dead-code-confidence }}%)..."
          VULTURE_OUTPUT=$(uv run vulture ${{ inputs.source-directory }}/ --min-confidence ${{ inputs.dead-code-confidence }} 2>&1) || true
```

Add an `env:` block to the step and update to:

```yaml
        env:
          SRC_DIR: ${{ inputs.source-directory }}
          DEAD_CODE_CONFIDENCE: ${{ inputs.dead-code-confidence }}
```

And change the run lines to:

```yaml
          echo "Scanning for dead code (min confidence: $DEAD_CODE_CONFIDENCE%)..."
          VULTURE_OUTPUT=$(uv run vulture "$SRC_DIR/" --min-confidence "$DEAD_CODE_CONFIDENCE" 2>&1) || true
```

Also update the step summary line that interpolates `dead-code-confidence`:
```yaml
          echo "**Found $DEAD_CODE_COUNT potential dead code issue(s)** (confidence >=$DEAD_CODE_CONFIDENCE%)" >> $GITHUB_STEP_SUMMARY
```

- [ ] **Step 7: Fix `|| echo` swallowing in Run integration tests step (around line 290)**

Find the `Run integration tests with coverage` step. The current `run:` block ends with:

```bash
            -v || echo "No integration tests found or all skipped"
```

Replace the entire `run:` block body to use the exit-code-5 pattern:

```yaml
        run: |
          echo "::group::Integration Test Execution"
          set +e
          uv run pytest \
            -m "integration" \
            --cov=${{ inputs.source-directory }} \
            --cov-report=xml:coverage-integration.xml \
            --cov-report=term-missing \
            --cov-branch \
            --cov-append \
            --junitxml=junit-integration.xml \
            -o junit_family=xunit2 \
            -v
          EXIT=$?
          set -e
          echo "::endgroup::"
          if [ $EXIT -ne 0 ] && [ $EXIT -ne 5 ]; then exit $EXIT; fi
```

Note: also apply the same SRC_DIR env-var substitution to the `--cov=` argument:
Add `env: SRC_DIR: ${{ inputs.source-directory }}` to the step and change `--cov=${{ inputs.source-directory }}` to `--cov="$SRC_DIR"`.

- [ ] **Step 8: Fix `|| echo` swallowing in Run security tests step (around line 304)**

Apply the same exit-code-5 pattern to the `Run security tests with coverage` step. Replace:

```bash
            -v || echo "No security tests found or all skipped"
```

With the same `set +e` / `EXIT=$?` / `set -e` / `if [ $EXIT -ne 0 ] && [ $EXIT -ne 5 ]; then exit $EXIT; fi` pattern as Step 7, including `SRC_DIR` env var substitution.

- [ ] **Step 9: Validate**

```bash
qlty check --plugin actionlint --plugin shellcheck \
  .github/workflows/python-ci.yml
```

Expected: no errors.

- [ ] **Step 10: Commit**

```bash
git add .github/workflows/python-ci.yml
git commit -m "fix(security): scope permissions and fix test error suppression in python-ci

Remove workflow-level pull-requests:write and checks:write. Apply env-var
isolation to source-directory, test-directory, python-version,
dead-code-confidence inputs. Replace || echo swallowing with exit-code-5
pattern so real pytest failures propagate correctly."
```

---

## Task 5 (Worktree B): `python-compatibility.yml` -- Env-Var Pattern and Package Validation

**Files:**
- Modify: `.github/workflows/python-compatibility.yml:195-212`

- [ ] **Step 1: Confirm the target lines**

```bash
grep -n "\${{ inputs\." .github/workflows/python-compatibility.yml
```

Expected: hits at lines ~198-212 (system dep install steps) and ~221-229 (test run step).

- [ ] **Step 2: Replace the Install system dependencies (Ubuntu) step (lines 195-200)**

Find:

```yaml
      - name: Install system dependencies (Ubuntu)
        if: runner.os == 'Linux' && inputs.system-deps-ubuntu != ''
        run: |
          echo "📦 Installing system dependencies: ${{ inputs.system-deps-ubuntu }}"
          sudo apt-get update
          sudo apt-get install -y ${{ inputs.system-deps-ubuntu }}
```

Replace with:

```yaml
      - name: Install system dependencies (Ubuntu)
        if: runner.os == 'Linux' && inputs.system-deps-ubuntu != ''
        env:
          SYSTEM_DEPS_UBUNTU: ${{ inputs.system-deps-ubuntu }}
        run: |
          echo "Installing system dependencies: $SYSTEM_DEPS_UBUNTU"
          if [[ ! "$SYSTEM_DEPS_UBUNTU" =~ ^[a-zA-Z0-9_\-\. ]+$ ]]; then
            echo "::error::Invalid package name characters in system-deps-ubuntu"
            exit 1
          fi
          sudo apt-get update
          sudo apt-get install -y $SYSTEM_DEPS_UBUNTU
```

- [ ] **Step 3: Replace the Install system dependencies (macOS) step (lines 202-206)**

Find:

```yaml
      - name: Install system dependencies (macOS)
        if: runner.os == 'macOS' && inputs.system-deps-macos != ''
        run: |
          echo "📦 Installing system dependencies: ${{ inputs.system-deps-macos }}"
          brew install ${{ inputs.system-deps-macos }}
```

Replace with:

```yaml
      - name: Install system dependencies (macOS)
        if: runner.os == 'macOS' && inputs.system-deps-macos != ''
        env:
          SYSTEM_DEPS_MACOS: ${{ inputs.system-deps-macos }}
        run: |
          echo "Installing system dependencies: $SYSTEM_DEPS_MACOS"
          if [[ ! "$SYSTEM_DEPS_MACOS" =~ ^[a-zA-Z0-9_\-\. ]+$ ]]; then
            echo "::error::Invalid package name characters in system-deps-macos"
            exit 1
          fi
          brew install $SYSTEM_DEPS_MACOS
```

- [ ] **Step 4: Replace the Install system dependencies (Windows) step (lines 208-213)**

Find:

```yaml
      - name: Install system dependencies (Windows)
        if: runner.os == 'Windows' && inputs.system-deps-windows != ''
        run: |
          echo "📦 Installing system dependencies: ${{ inputs.system-deps-windows }}"
          choco install ${{ inputs.system-deps-windows }} -y
        shell: pwsh
```

Replace with:

```yaml
      - name: Install system dependencies (Windows)
        if: runner.os == 'Windows' && inputs.system-deps-windows != ''
        env:
          SYSTEM_DEPS_WINDOWS: ${{ inputs.system-deps-windows }}
        run: |
          if ($env:SYSTEM_DEPS_WINDOWS -notmatch '^[a-zA-Z0-9_\-\. ]+$') {
            Write-Error "Invalid package name characters in system-deps-windows"
            exit 1
          }
          choco install $env:SYSTEM_DEPS_WINDOWS -y
        shell: pwsh
```

- [ ] **Step 5: Apply env-var pattern to the Run tests step (around line 218)**

Find the `Run tests` step and add:

```yaml
        env:
          TEST_COMMAND: ${{ inputs.test-command }}
          SRC_DIR: ${{ inputs.source-directory }}
          PYTHON_VER: ${{ matrix.python }}
          RUNNER_OS: ${{ matrix.os }}
```

Replace `${{ inputs.test-command }}` with `$TEST_COMMAND`, `${{ inputs.source-directory }}` with `$SRC_DIR`, `${{ matrix.python }}` with `$PYTHON_VER`, `${{ matrix.os }}` with `$RUNNER_OS` in the run: block.

- [ ] **Step 6: Validate**

```bash
qlty check --plugin actionlint --plugin shellcheck \
  .github/workflows/python-compatibility.yml
```

Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add .github/workflows/python-compatibility.yml
git commit -m "fix(security): env-var isolation and package name validation in python-compatibility

Move system-deps-* inputs to env: blocks. Add allowlist regex validation
before sudo/brew/choco install to reject inputs with shell-special characters."
```

---

## Task 6 (Worktree B): `python-docs.yml` -- Permission Scoping, Remove Redundant Cache, Add Harden-Runner to Deploy

**Files:**
- Modify: `.github/workflows/python-docs.yml:50-53, 85-89, 113-144`

- [ ] **Step 1: Remove `id-token: write` from workflow-level permissions (line 53)**

Find:

```yaml
permissions:
  contents: read
  pages: write
  id-token: write
```

Replace with:

```yaml
permissions:
  contents: read
  pages: write
```

The `id-token: write` is already correctly scoped at the `deploy` job level (line 121) -- no additional change needed there.

- [ ] **Step 2: Remove the redundant `actions/cache` step (lines 85-89)**

The `setup-uv` action at lines 79-83 already has `enable-cache: true` which provides built-in uv caching. Delete this step entirely:

```yaml
      - name: Cache dependencies
        uses: actions/cache@27d5ce7f107fe9357f9df03efb73ab90386fccae  # v5.0.5
        with:
          path: .venv
          key: venv-${{ runner.os }}-${{ hashFiles('**/uv.lock') }}-docs
```

- [ ] **Step 3: Also apply env-var pattern to the Check docstring coverage step (line 94)**

Find:

```yaml
      - name: Check docstring coverage
        run: |
          echo "📝 Checking docstring coverage..."
          uv run interrogate ${{ inputs.source-directory }} \
            --fail-under=${{ inputs.docstring-threshold }} \
            --verbose || echo "⚠️  Docstring coverage below threshold"
```

Replace with:

```yaml
      - name: Check docstring coverage
        env:
          SRC_DIR: ${{ inputs.source-directory }}
          DOCSTRING_THRESHOLD: ${{ inputs.docstring-threshold }}
        run: |
          echo "Checking docstring coverage..."
          uv run interrogate "$SRC_DIR" \
            --fail-under="$DOCSTRING_THRESHOLD" \
            --verbose || echo "Docstring coverage below threshold"
```

- [ ] **Step 4: Add harden-runner as first step in the `deploy` job (line 127)**

The `deploy` job currently has no `harden-runner` step. Add it as the first step after the job's `steps:` key:

```yaml
    steps:
      - name: Harden Runner
        uses: step-security/harden-runner@8d3c67de8e2fe68ef647c8db1e6a09f647780f40  # v2.19.0
        with:
          egress-policy: audit
          allowed-endpoints: api.github.com:443

      - name: Download documentation artifacts
```

- [ ] **Step 5: Validate**

```bash
qlty check --plugin actionlint --plugin shellcheck \
  .github/workflows/python-docs.yml
```

Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/python-docs.yml
git commit -m "fix(security): scope id-token permission and harden deploy job in python-docs

Remove id-token:write from workflow level (already at deploy job level).
Remove redundant actions/cache (setup-uv enable-cache covers this).
Add harden-runner to deploy job. Apply env-var pattern to source-directory
and docstring-threshold inputs."
```

---

## Task 7 (Worktree B): `python-release.yml` -- Permission Scoping and Artifact Upload Fix

**Files:**
- Modify: `.github/workflows/python-release.yml:99-104, 154-165, 266-271`

- [ ] **Step 1: Replace workflow-level permissions (lines 99-104)**

Find:

```yaml
permissions:
  contents: write
  issues: write
  pull-requests: write
  id-token: write
  attestations: write
```

Replace with:

```yaml
permissions:
  contents: read
```

- [ ] **Step 2: Add job-level permissions to the `release` job (line 154)**

Find the `release:` job definition (line 154). After `timeout-minutes: 15`, add:

```yaml
    permissions:
      contents: write
      id-token: write
      attestations: write
```

The full job opening should look like:

```yaml
  release:
    name: Build & Release
    needs: test
    if: always() && (needs.test.result == 'success' || needs.test.result == 'skipped')
    runs-on: ubuntu-latest
    timeout-minutes: 15
    permissions:
      contents: write
      id-token: write
      attestations: write
    outputs:
```

- [ ] **Step 3: Find and add job-level permissions to the `publish-pypi` job**

Read the file to find the `publish-pypi` job definition:

```bash
grep -n "^  publish-pypi:\|^  publish_pypi:" .github/workflows/python-release.yml
```

Add `permissions: id-token: write` to that job block in the same manner as Step 2.

- [ ] **Step 4: Add `if: always()` to the artifact upload step (line 266)**

Find:

```yaml
      - name: Upload distribution artifacts
        uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a  # v7.0.1
        with:
          name: release-dist
          path: dist/
          retention-days: 5
```

Replace with:

```yaml
      - name: Upload distribution artifacts
        if: always()
        uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a  # v7.0.1
        with:
          name: release-dist
          path: dist/
          retention-days: 5
```

- [ ] **Step 5: Validate**

```bash
qlty check --plugin actionlint --plugin shellcheck \
  .github/workflows/python-release.yml
```

Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/python-release.yml
git commit -m "fix(security): scope permissions to jobs and add if:always() to artifact upload

Move contents:write, id-token:write, attestations:write to release job.
Move id-token:write to publish-pypi job. Remove issues:write and
pull-requests:write (no job uses them). Workflow-level reduced to
contents:read. Add if:always() to artifact upload to preserve build
artifacts on release failure."
```

---

## Task 8 (Worktree B): `python-security-analysis.yml` -- Boolean Heredoc Inputs to Env Vars

**Files:**
- Modify: `.github/workflows/python-security-analysis.yml:281-365`

The `Analyze OSV Results` step (line 281) uses `${{ inputs.fail-on-high }}` and `${{ inputs.fail-on-medium }}` as Python string comparisons inside a heredoc. These are injected as raw strings.

- [ ] **Step 1: Confirm the injection points**

```bash
grep -n "inputs\.fail-on" .github/workflows/python-security-analysis.yml
```

Expected: hits at lines 358 and 364 inside the `python3 << 'EOF'` block.

- [ ] **Step 2: Add `env:` block to the Analyze OSV Results step and update Python code**

Find the `Analyze OSV Results` step (line ~281). It currently has no `env:` block. Add one and update the two Python comparisons.

The step opening becomes:

```yaml
      - name: Analyze OSV Results
        env:
          FAIL_ON_HIGH: ${{ inputs.fail-on-high }}
          FAIL_ON_MEDIUM: ${{ inputs.fail-on-medium }}
        run: |
          echo "Analyzing OSV scan results..."
          python3 << 'EOF'
          import json
          import os
          import sys
```

Replace line 358 (`if '${{ inputs.fail-on-high }}' == 'true':`) with:

```python
                  if os.environ.get("FAIL_ON_HIGH", "false").lower() == "true":
```

Replace line 364 (`if '${{ inputs.fail-on-medium }}' == 'true':`) with:

```python
                  if os.environ.get("FAIL_ON_MEDIUM", "false").lower() == "true":
```

- [ ] **Step 3: Validate**

```bash
qlty check --plugin actionlint --plugin shellcheck \
  .github/workflows/python-security-analysis.yml
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/python-security-analysis.yml
git commit -m "fix(security): move boolean heredoc inputs to env vars in python-security-analysis

fail-on-high and fail-on-medium were interpolated as Python string literals
inside the OSV scanner heredoc. Now read via os.environ to prevent injection."
```

---

## Task 9 (Worktree B): `python-pr-validation.yml` -- Env-Var Pattern for String Inputs

**Files:**
- Modify: `.github/workflows/python-pr-validation.yml`

Note: Phase 2 replaces this workflow's entire job content with a hard-fail migration job. This task only hardens the existing inputs in Phase 1 so no unquoted interpolations exist in the interim.

- [ ] **Step 1: Find all unquoted input interpolations in run: blocks**

```bash
grep -n "\${{ inputs\." .github/workflows/python-pr-validation.yml | grep -v "^[0-9]*:#"
```

Review each hit. For any `${{ inputs.<name> }}` appearing inside a `run:` block (not in `if:`, `with:`, or other YAML keys), apply the env-var pattern.

- [ ] **Step 2: For each run: step that interpolates string inputs, add an env: block**

For each affected step, the pattern is:

```yaml
        env:
          INPUT_NAME: ${{ inputs.input-name }}
        run: |
          command "$INPUT_NAME"
```

Apply this to every step found in Step 1. Common inputs in this file:
- `python-version` (used in uv python install)
- `source-directory` (used in test commands)
- `test-directory` (used in test commands)
- `min-description-length` (used in validation logic)
- `coverage-threshold` (used in pytest)

- [ ] **Step 3: Validate**

```bash
qlty check --plugin actionlint --plugin shellcheck \
  .github/workflows/python-pr-validation.yml
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/python-pr-validation.yml
git commit -m "fix(security): env-var isolation for string inputs in python-pr-validation

Apply env: block pattern to all run: steps that interpolate string inputs.
Note: this workflow's job content will be replaced by a hard-fail migration
job in Phase 2 (fix/workflow-architecture-cleanup)."
```

---

## Task 10 (Worktree B): `python-slsa.yml` -- SHA-Pin Comment Examples and Add Header Note

**Files:**
- Modify: `.github/workflows/python-slsa.yml:1-53`

The comment block at lines 17-25 uses mutable `@v4` tags in the usage example, which defeats the SHA-pinning intent for callers copying this template.

- [ ] **Step 1: Replace mutable tags in comment examples (lines 17-25)**

Find:

```yaml
#         - uses: actions/checkout@v4
#         - run: pip install build && python -m build
#         - id: hash
#           run: |
#             cd dist && echo "hashes=$(sha256sum * | base64 -w0)" >> "$GITHUB_OUTPUT"
#         - uses: actions/upload-artifact@v4
```

Replace with:

```yaml
#         - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd  # v6.0.2
#         - run: pip install build && python -m build
#         - id: hash
#           run: |
#             cd dist && echo "hashes=$(sha256sum * | base64 -w0)" >> "$GITHUB_OUTPUT"
#         - uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a  # v7.0.1
```

- [ ] **Step 2: Add SLSA-not-included note to the header**

After the existing header comment block (before the closing `# ===` line), add:

```yaml
# IMPORTANT: SLSA provenance is NOT included in python-release.yml.
# Every caller must add the provenance job from this template directly
# into their own top-level release workflow. GitHub Actions prohibits
# nested reusable workflow calls, so this job cannot be called from
# python-release.yml.
```

- [ ] **Step 3: Validate**

```bash
qlty check --plugin actionlint \
  .github/workflows/python-slsa.yml
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/python-slsa.yml
git commit -m "fix(supply-chain): SHA-pin comment examples and add SLSA-not-included warning

Replace @v4 mutable tags in template examples with pinned SHAs.
Add prominent note that SLSA provenance must be added to each caller's
own top-level workflow -- it cannot be nested inside python-release.yml."
```

---

## Task 11 (Worktree B): `python-publish-pypi.yml` -- Replace Unpinned Safety with pip-audit

**Files:**
- Modify: `.github/workflows/python-publish-pypi.yml:92-106`

The `Run security checks` step uses `pip install safety bandit` (unpinned, network fetch) and suppresses failures with `|| echo`.

- [ ] **Step 1: Confirm the target block**

```bash
sed -n '90,110p' .github/workflows/python-publish-pypi.yml
```

Expected: the `pip install safety bandit` block at lines 92-106.

- [ ] **Step 2: Replace the Run security checks step**

Find:

```yaml
      - name: Run security checks
        if: ${{ inputs.run-security-checks }}
        run: |
          echo "🔒 Running pre-publish security checks..."

          # Install security tools
          pip install safety bandit

          # Check for known vulnerabilities in dependencies
          echo "📦 Checking dependencies for vulnerabilities..."
          safety check || echo "⚠️  Safety check found issues - review before publishing"

          # Scan source code for security issues
          echo "🔍 Scanning source code..."
          bandit -r ${{ inputs.source-directory }} -ll || echo "⚠️  Bandit found issues - review before publishing"
```

Replace with:

```yaml
      - name: Run security checks
        if: ${{ inputs.run-security-checks }}
        env:
          SRC_DIR: ${{ inputs.source-directory }}
        run: |
          echo "Running pre-publish security checks..."
          uv run pip-audit --strict
          uv run bandit -r "$SRC_DIR" -c pyproject.toml -ll
```

- [ ] **Step 3: Validate**

```bash
qlty check --plugin actionlint --plugin shellcheck \
  .github/workflows/python-publish-pypi.yml
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/python-publish-pypi.yml
git commit -m "fix(supply-chain): replace unpinned safety with pip-audit in python-publish-pypi

Remove pip install safety bandit (unpinned, error-suppressed). Replace with
uv run pip-audit --strict (hard fail on any vulnerability) and
uv run bandit -r SRC_DIR -c pyproject.toml -ll (respects pyproject.toml config)."
```

---

## Task 12 (Worktree B): `python-docker.yml` -- Enable-SBOM Default and Provenance Input

**Files:**
- Modify: `.github/workflows/python-docker.yml:131-135, 285-299`

- [ ] **Step 1: Flip `enable-sbom` default to `true` (lines 131-135)**

Find:

```yaml
      enable-sbom:
        description: 'Generate Software Bill of Materials'
        type: boolean
        required: false
        default: false
```

Replace with:

```yaml
      enable-sbom:
        description: 'Generate Software Bill of Materials'
        type: boolean
        required: false
        default: true
```

- [ ] **Step 2: Add new `enable-provenance` input after `enable-sbom`**

After the `enable-sbom` input block, add:

```yaml
      enable-provenance:
        description: 'Generate SLSA provenance attestation for the Docker image'
        type: boolean
        required: false
        default: true
```

- [ ] **Step 3: Update the build-push-action step to use separate provenance input (line 299)**

Find:

```yaml
          sbom: ${{ inputs.enable-sbom }}
          provenance: ${{ inputs.enable-sbom }}
```

Replace with:

```yaml
          sbom: ${{ inputs.enable-sbom }}
          provenance: ${{ inputs.enable-provenance }}
```

- [ ] **Step 4: Validate**

```bash
qlty check --plugin actionlint --plugin shellcheck \
  .github/workflows/python-docker.yml
```

Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/python-docker.yml
git commit -m "fix(supply-chain): enable SBOM and provenance by default in python-docker

Flip enable-sbom default from false to true. Add enable-provenance input
(default: true) separate from enable-sbom so callers can control each
independently. Callers that previously relied on the false default must add
enable-sbom: false explicitly."
```

---

## Task 13: Final Validation of Worktree B

- [ ] **Step 1: Run pre-commit across all files**

From `.worktrees/fix-workflow-input-quoting`:

```bash
pre-commit run --all-files
```

Expected: all hooks pass.

- [ ] **Step 2: Run qlty across all modified workflows**

```bash
qlty check --plugin actionlint --plugin shellcheck \
  .github/workflows/python-ci.yml \
  .github/workflows/python-compatibility.yml \
  .github/workflows/python-docs.yml \
  .github/workflows/python-release.yml \
  .github/workflows/python-security-analysis.yml \
  .github/workflows/python-pr-validation.yml \
  .github/workflows/python-slsa.yml \
  .github/workflows/python-publish-pypi.yml \
  .github/workflows/python-docker.yml
```

Expected: no errors across all nine files.

- [ ] **Step 3: Confirm no unquoted inputs remain**

```bash
grep -rn "\${{ inputs\." .github/workflows/python-ci.yml \
  .github/workflows/python-compatibility.yml \
  .github/workflows/python-docs.yml \
  .github/workflows/python-release.yml \
  .github/workflows/python-security-analysis.yml \
  .github/workflows/python-pr-validation.yml \
  .github/workflows/python-publish-pypi.yml \
  .github/workflows/python-docker.yml | grep -v "^[^:]*:#" | grep "run:" -A5
```

Review output. Any remaining `${{ inputs.* }}` hits inside `run:` blocks that are not in an `env:` key are injection risks. Fix each before proceeding.

---

## Task 14: Merge Worktrees into Integration Branch

Work directory: `/home/byron/dev/.github` (the main worktree, on `main`)

- [ ] **Step 1: Final validation of Worktree A**

```bash
cd .worktrees/fix-perf-regression-rce
pre-commit run --all-files
qlty check --plugin actionlint --plugin shellcheck \
  .github/workflows/python-performance-regression.yml
```

Expected: all pass.

- [ ] **Step 2: Merge Worktree A into the integration branch**

```bash
git checkout fix/workflow-security-remediation
git merge --no-ff fix/perf-regression-rce \
  -m "merge: worktree A -- python-performance-regression.yml CRIT fixes"
```

- [ ] **Step 3: Merge Worktree B into the integration branch**

```bash
git merge --no-ff fix/workflow-input-quoting \
  -m "merge: worktree B -- systematic env-var sweep and supply chain fixes"
```

If merge conflicts occur: they will only appear in files touched by both worktrees. Worktree A touches only `python-performance-regression.yml`; Worktree B does not touch that file. No conflicts are expected.

- [ ] **Step 4: Run final end-to-end validation on integration branch**

```bash
pre-commit run --all-files
qlty check --plugin actionlint --plugin shellcheck .github/workflows/
```

Expected: all pass.

- [ ] **Step 5: Confirm success criteria**

```bash
# No unquoted inputs in any run: block
grep -rn "\${{ inputs\." .github/workflows/ | grep -v "^[^:]*:#"
```

Manually review hits. All should appear in `if:`, `with:`, `env:`, or other non-shell contexts. No hits should appear directly inside shell command lines.

```bash
# synthetic-data-script input removed
grep -rn "synthetic-data-script" .github/workflows/
```

Expected: no output.

```bash
# Docker enable-sbom defaults true
grep -n "enable-sbom" .github/workflows/python-docker.yml
```

Expected: `default: true` on the enable-sbom input.

- [ ] **Step 6: Clean up worktrees**

```bash
git worktree remove .worktrees/fix-perf-regression-rce
git worktree remove .worktrees/fix-workflow-input-quoting
```

- [ ] **Step 7: Push and open PR**

```bash
git push origin fix/workflow-security-remediation
gh pr create \
  --base main \
  --head fix/workflow-security-remediation \
  --title "fix(security): eliminate input injection vectors and harden supply chain" \
  --body "$(cat <<'EOF'
## Summary

- CRIT-01: Remove \`synthetic-data-script\` RCE input from python-performance-regression.yml; callers use \`scripts/generate_test_data.py\` convention
- CRIT-02: Move all Python heredoc inputs to \`env:\` blocks, read via \`os.environ\`
- HIGH-05: Move benchmark shell inputs to env vars with quoted references
- Systematic env-var isolation across python-ci, python-compatibility, python-docs, python-release, python-security-analysis, python-pr-validation
- Permission scoping: workflow-level over-grants moved to individual jobs
- Exit-code-5 fix: pytest \`|| echo\` suppression replaced with proper exit code check
- Supply chain: Docker SBOM/provenance defaults flipped to \`true\`; unpinned safety replaced with pip-audit; SLSA comment examples SHA-pinned

## Breaking Change

\`python-docker.yml\`: \`enable-sbom\` default changed from \`false\` to \`true\`. Callers that intentionally disabled SBOM must add \`enable-sbom: false\` explicitly.

## Test Plan

- [ ] qlty check (actionlint + shellcheck) passes on all 10 modified workflows
- [ ] pre-commit run --all-files passes
- [ ] No \`\${{ inputs.* }}\` remains unquoted in any run: shell block
- [ ] \`synthetic-data-script\` input does not exist in any workflow
- [ ] python-release.yml artifact upload step has \`if: always()\`
- [ ] Trigger modified workflows via workflow_dispatch on a downstream test repo

Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-Review

### Spec coverage check

| Spec requirement | Task |
| --- | --- |
| Remove synthetic-data-script (CRIT-01) | Task 1 |
| Move all heredoc inputs to env vars (CRIT-02) | Task 2 |
| benchmark inputs to env vars (HIGH-05) | Task 3 |
| python-ci.yml: env-var pattern for source-directory, test-directory, python-version, dead-code-confidence | Task 4 steps 2-6 |
| python-ci.yml: move pull-requests:write, checks:write from workflow level | Task 4 step 1 |
| python-ci.yml: fix or true swallowing with exit-code-5 pattern | Task 4 steps 7-8 |
| python-compatibility.yml: env-var pattern + pattern validation | Task 5 |
| python-docs.yml: move id-token:write to deploy job, remove cache, add harden-runner | Task 6 |
| python-release.yml: move all permissions to job level, remove issues:write, if:always() on upload | Task 7 |
| python-security-analysis.yml: boolean heredoc inputs to env vars | Task 8 |
| python-pr-validation.yml: env-var pattern | Task 9 |
| python-slsa.yml: SHA-pin examples, SLSA-not-included note | Task 10 |
| python-publish-pypi.yml: replace safety with pip-audit | Task 11 |
| python-docker.yml: enable-sbom default true, enable-provenance input | Task 12 |
| End-to-end validation and PR | Tasks 13-14 |

All spec requirements for Phase 1 are covered. No gaps found.
