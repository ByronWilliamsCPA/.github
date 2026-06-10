# Handoff: python-release.yml `no-build` default breaks releases for packaged repos

> **Date**: 2026-06-10
> **Author**: Claude Code session in homelab-infra (Byron)
> **Affected workflow**: `.github/workflows/python-release.yml`
> **Severity**: High; release automation is fully broken for every caller repo that has a `[build-system]` in `pyproject.toml` and does not override the `no-build` input

## 1. One-paragraph context

`python-release.yml` exposes a `no-build` input (lines 100-104) that defaults to `true` and expands to `--no-build` on every `uv sync` and `uv run` invocation in both the `test` and `release` jobs. `uv sync` installs the caller's own project in editable mode by default, and an editable install (`editable+.`) can never have a binary distribution, so `--no-build` makes the project uninstallable. Every caller repo that is an actual Python package fails the "Install dependencies (uv with lockfile)" step before any release logic runs.

## 2. Why this matters now

homelab-infra had three consecutive `Release Pipeline / Build & Release` failures on main on 2026-06-10 (08:15, 13:03, and run [27281370868](https://github.com/ByronWilliamsCPA/homelab-infra/actions/runs/27281370868) at 13:55), all with:

```text
uv sync --all-extras --frozen $NO_BUILD_FLAG
error: Distribution `homelab-infra==0.1.0 @ editable+.` can't be installed
       because it is marked as `--no-build` but has no binary distribution
```

No release can be cut from that repo until either the caller passes `no-build: false` or this workflow changes. Other packaged caller repos in the org are presumably failing the same way [VERIFY: list caller repos and check which have a `[build-system]` table].

## 3. Current state, with line references

All references are against `origin/main` at `987d517`.

**File**: `.github/workflows/python-release.yml`

- Lines 100-104: the input. Note the description already acknowledges the problem case:

  ```yaml
  no-build:
    description: 'Pass --no-build to uv sync/run commands (disable for projects with a build backend like hatchling)'
    required: false
    type: boolean
    default: true
  ```

- Lines 130 and 233: `NO_BUILD_FLAG: ${{ inputs.no-build && '--no-build' || '' }}` in the `test` and `release` jobs.
- Line 180 (`test` job) and line 327 (`release` job): `uv sync --all-extras --frozen $NO_BUILD_FLAG`. Line 327 is the step that failed in the homelab-infra runs.
- Lines 188, 205, 215, 221, 335: further `$NO_BUILD_FLAG` uses on `uv sync` (no-lock path) and `uv run` (pytest, basedpyright, ruff).

**Regression history** (this exact failure was fixed once before):

- PR #107 (`3d29e7c`): "remove --no-build from uv sync in all reusable workflows".
- PR #160 (`5f67a99`): reintroduced it as the `no-build` input with `default: true`.

**Why default-true only works for non-packaged repos**: `uv sync` skips installing the project itself only when the project is not a package (no `[build-system]`, or `tool.uv.package = false`). For every repo with a build backend, the project is installed editable and `--no-build` is guaranteed to fail. The default therefore matches the wrong case: packaged repos are exactly the ones that use a release workflow.

**Caller-side workaround** (already being applied to homelab-infra): pass `no-build: false` in the caller. This restores releases but leaves the foot-gun default in place for the next repo.

## 4. Three options, with concrete trade-offs

The GOAL for any option: a caller repo with a build backend must get a working dependency install in both jobs by default, while non-packaged repos keep the wheels-only hardening that `--no-build` provides. Mechanisms below are suggestions, not verified implementations.

### Option 1 (recommended): flip the default to `false`

**What changes**: one line, `default: true` to `default: false` at line 104. Update the description to say opt-in. Non-packaged repos that want wheels-only installs opt in explicitly.

**Pros**: restores the post-#107 known-good behavior; zero risk for packaged repos; smallest diff.

**Cons**: callers that currently rely on the hardening silently lose it unless they opt in [VERIFY: grep org repos for existing `no-build:` usage in callers; if none pass it explicitly, nobody loses anything].

**Verification this is safe**: re-run the homelab-infra release workflow after the change; the install step at line 327 should pass without caller changes.

### Option 2: keep the flag but stop applying it to the project itself

**What changes**: where `NO_BUILD_FLAG` is set on `uv sync`, pair it with `--no-install-project`, then the project's own editable build is skipped entirely. The `release` job's later packaging step builds the artifact independently, so the project does not need to be importable there [VERIFY: confirm the release job's build/publish steps do not import the package]. The `test` job CANNOT use `--no-install-project` naively: pytest imports the package under test, so for src layouts the project must be installed or the tests collected via path manipulation. The test job would need `--no-build-package` exclusions or to drop the flag.

**Pros**: keeps wheels-only hardening for third-party dependencies everywhere.

**Cons**: asymmetric flags across jobs; the test-job caveat makes this materially more complex than Option 1; `uv` flag semantics need verification against the pinned uv version [VERIFY: `uv sync --help` for `--no-install-project` and `--no-build-package` availability].

### Option 3: auto-detect the build backend

**What changes**: the existing repo-state detection step (which already distinguishes uv-locked / uv-no-lock / skip) additionally greps `pyproject.toml` for `[build-system]`; when present, force the flag off regardless of input.

**Pros**: zero caller changes; correct by construction for both repo classes.

**Cons**: more workflow logic; detection by grep can be fooled by comments [VERIFY: prefer a TOML-aware check if a Python step is already available]; input semantics become "request, not command", which needs documenting.

## 5. Coupled edits whichever option is chosen

- The `NOSONAR(S8541,S8544)` comments at lines 183-188, 204, 215, 221, 330-335 exist specifically to justify `$NO_BUILD_FLAG` indirection to SonarCloud; revisit or remove them if the flag handling changes.
- An in-flight branch `chore/fix-psr-release-bugs` ("apply PSR v10.5.3 bug mitigations to reusable workflow") touches this same file; coordinate to avoid conflicts.
- The cryptic failure mode deserves a fast-fail guard regardless of option: a preflight step that detects `[build-system]` + `no-build: true` and emits `::error::` naming the input would have turned a multi-run mystery into a one-line diagnosis.
- CHANGELOG entry and conventional commit type `fix(python-release)` per repo convention.

## 6. How to resume

1. `git fetch origin main` and confirm lines cited in section 3 still match (`git show origin/main:.github/workflows/python-release.yml | grep -n NO_BUILD_FLAG`).
2. Pick an option (Option 1 unless there is a known consumer of the default-true hardening).
3. Apply, PR, merge.
4. Verify: trigger the homelab-infra release workflow (it calls this workflow pinned to a main SHA; the caller pin at `homelab-infra/.github/workflows/release.yml:52` must be bumped to the fixed SHA, or wait for Renovate to bump it). Expect the Build & Release install step to pass. Note homelab-infra may already carry the caller-side `no-build: false` workaround by then, which masks the org-side verification; test against a second packaged caller repo if so.

## 7. Gotchas

- The homelab-infra failures are NOT caused by the repo's recent commits; the failure is in dependency installation before any project code runs. Do not chase the triggering commits.
- `gh run view --log-failed` on these runs buries the error under container-build apt output and StepSecurity agent logs; grep the full log for `error:` or `uv sync` instead.
- The `test` job (Pre-Release Tests) was skipped in the observed homelab-infra runs (`run-tests` evaluated false), so the same `--no-build` failure in the `test` job at line 180 has not yet been observed in the wild but is latent for any caller that enables tests.
