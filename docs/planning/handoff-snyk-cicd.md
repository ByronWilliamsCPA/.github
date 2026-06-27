# Handoff: Snyk CI/CD Extension

**Repo:** ByronWilliamsCPA/.github (working dir: ~/dev/.github)
**Base branch:** claude/snyk-integration-0
**Next branch:** claude/snyk-iac-aibom-1
**Session date:** 2026-06-25

---

## Context

The `claude/snyk-integration-0` branch (not yet merged) added the initial Snyk
reusable workflow layer. Before starting this work, read that branch:

```bash
git checkout claude/snyk-integration-0
```

Files on that branch:
- `.github/workflows/python-snyk.yml` -- reusable workflow: Snyk Code (SAST),
  optional OSS advisory, optional AI-BOM
- `.github/workflows/python-standard-stack.yml` -- added `run-snyk: false`
  input, forwarded `SNYK_TOKEN` secret
- `.github/workflows/self-test.yml` -- added `test-python-snyk` job
- `docs/planning/adr/adr-003-snyk-ai-code-security.md` -- decision record
- `docs/workflows/python-snyk.md` -- operator guide

The evaluation compared Snyk against Cycode, Checkmarx One, and Endor Labs.
Snyk was selected. The full comparison JSON is in the scratchpad at:
`/tmp/claude-1000/-home-byron-dev--github/b617e56f-1680-44d7-83bc-ff79cc722db5/scratchpad/security-tool-comparison.json`

---

## What is NOT yet implemented (this session's scope)

### 1. IaC scanning workflow (HIGH priority, HIGH value)

The baseline stack has no IaC scanner. Snyk IaC fills three gaps simultaneously:
Terraform, Kubernetes manifests, and Docker Compose. All are rated HIGH in the
comparison because the baseline is completely absent.

**Create** `.github/workflows/python-snyk-iac.yml` as a new reusable workflow.
Model it on `python-snyk.yml`'s structure (token-gated no-op, detect-config job
pattern). Jobs needed:

- `detect-iac`: check SNYK_TOKEN via env var (not `secrets.SNYK_TOKEN` in an
  `if:` expression -- that is the secrets-in-if antipattern documented in
  memory). Check whether any .tf / k8s YAML / docker-compose*.yml files exist
  under the configured directories.
- `snyk-terraform`: `snyk iac test <terraform-dirs> --sarif-file-output=iac-terraform.sarif`
- `snyk-kubernetes`: `snyk iac test <k8s-dirs> --sarif-file-output=iac-k8s.sarif`
- `snyk-compose`: `snyk iac test <compose-dirs> --sarif-file-output=iac-compose.sarif`

Each job should upload its SARIF via `github/codeql-action/upload-sarif@v3`.

Inputs needed:
- `terraform-dirs` (string, default: `.`) -- space-separated dirs to scan
- `k8s-dirs` (string, default: ``) -- empty string = skip k8s job
- `compose-dirs` (string, default: ``) -- empty string = skip compose job
- `fail-on-high` (bool, default: true)

Token input: `SNYK_TOKEN` (required: false; skip all jobs if absent).

**Tag RAD markers** on: permission scopes for SARIF upload
(`security-events: write` must be at caller-job level), SNYK_TOKEN absent
behavior, directory glob edge cases.

**Create** `docs/workflows/python-snyk-iac.md` following the same structure
as `docs/workflows/python-snyk.md`. Include an example caller block for
homelab-infra (the primary Terraform target).

**Update** `docs/workflows/python-standard-stack.md` to reference the new
IaC workflow as a separate opt-in call (it cannot be absorbed into
`python-standard-stack.yml` because most Python repos have no IaC files).

**Add a self-test job** to `.github/workflows/self-test.yml` scanning the
`scripts/` directory with `fail-on-high: false`.

### 2. AI-BOM shortcut in python-standard-stack (MEDIUM priority)

Current state: `python-snyk.yml` has `run-aibom: false` as an input, but
`python-standard-stack.yml` does not expose this input. To enable AI-BOM via
the standard stack, callers today must call `python-snyk.yml` directly.

**Add** `enable-aibom: false` input to `python-standard-stack.yml`. Forward it
to the `snyk` job's `run-aibom` input. This is a one-line addition to the snyk
job's `with:` block. No new workflow file needed.

**Update** `docs/workflows/python-standard-stack.md` to document the new input.

**ADR-003 update**: The current ADR notes that AI-BOM requires a direct caller.
Add a "Status" note that this restriction was lifted by adding `enable-aibom`
to `python-standard-stack.yml`.

### 3. Exploit maturity / pre-NVD notes (LOW priority, documentation only)

Snyk's exploit maturity fields (isExploitable, exploitMaturity) are surfaced in
`snyk test --json` output automatically on any paid plan. The `python-snyk.yml`
OSS advisory job already runs `snyk test`; no workflow change is needed.

Document in `docs/workflows/python-snyk.md` (under a "Reading Results" section)
that the Snyk dashboard exposes exploit maturity and that the pre-NVD window
is the primary reason to run `snyk-oss` even when Renovate is the fix-PR source.

### 4. MCP Scan (DO NOT IMPLEMENT YET)

Snyk MCP Scan (from the Invariant Labs acquisition) is pre-GA as of 2026-06.
Add a stub section in ADR-003 under "Future Decisions" noting this capability
and the condition for implementation: GA announcement in the Snyk changelog.

---

## Implementation order

1. Create branch: `git checkout -b claude/snyk-iac-aibom-1 claude/snyk-integration-0`
2. Write `python-snyk-iac.yml`
3. Add self-test job for IaC
4. Add `enable-aibom` to `python-standard-stack.yml`
5. Write `docs/workflows/python-snyk-iac.md`
6. Update `docs/workflows/python-snyk.md` (Reading Results section)
7. Update ADR-003 (remove direct-caller restriction, add MCP Scan stub)
8. Run `pre-commit run --all-files`
9. Commit with signed commit, conventional commit format

---

## Key constraints

- **Secrets-in-if antipattern**: Never write `if: ${{ secrets.SNYK_TOKEN == '' }}`.
  Use `env: HAS_TOKEN: ${{ secrets.SNYK_TOKEN != '' }}` then `if: env.HAS_TOKEN == 'true'`
  in the step, or the detect-config pattern from `python-snyk.yml`.
- **startup_failure**: Callers must grant `security-events: write` at the calling-job
  level (not workflow level) or the reusable starts with `startup_failure` before any
  job runs. See ADR-003 #CRITICAL note and memory entry "Reusable startup_failure causes".
- **No em-dashes** in any file content (pre-commit hook will block the commit).
- **uv-only org policy**: The IaC workflow needs no Python dependency resolution;
  this constraint does not apply to `python-snyk-iac.yml`.
- **Branch naming**: `claude/<description>-<id>` format.
- **Signed commits**: `git commit -S` on every commit.
