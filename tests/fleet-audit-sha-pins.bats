#!/usr/bin/env bats
# =============================================================================
# Tests for scripts/fleet-audit-sha-pins.sh
# =============================================================================
# Covers: basic audit invocation, CSV output format, violation counting,
# and report-only semantics. All tests are isolated and require no network access.
#
# Mocking strategy: the script uses the "gh" CLI exclusively for API calls.
# We install a fake "gh" binary first on PATH. The stub honours the --jq
# flag the same way the rest of the suite does (via _apply_jq_flag).

load 'libs/bats-support/load'
load 'libs/bats-assert/load'

SCRIPT="$BATS_TEST_DIRNAME/../scripts/fleet-audit-sha-pins.sh"

# Fake 40-char SHA used in the clean-repo workflow.
CLEAN_SHA="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"  # pragma: allowlist secret

# ---------------------------------------------------------------------------
# setup / teardown
# ---------------------------------------------------------------------------

setup() {
  TEST_TMPDIR="$(mktemp -d)"
  GH_BIN="$TEST_TMPDIR/bin"
  mkdir -p "$GH_BIN"
  export PATH="$GH_BIN:/usr/local/bin:/bin:/usr/bin"
  export TEST_TMPDIR
  export CLEAN_SHA
}

teardown() { rm -rf "$TEST_TMPDIR"; }

# ---------------------------------------------------------------------------
# Stub helpers
# ---------------------------------------------------------------------------
# The script calls "gh" with patterns like:
#
#   gh auth status
#   gh repo list ORG --limit 200 --json name --jq FILTER
#   gh api repos/ORG/REPO/contents/.github/workflows --jq FILTER
#   gh api repos/ORG/REPO/contents/.github/workflows/FILE.yml --jq FILTER
#
# _apply_jq_flag is exported by the test harness (defined in
# update-pinned-actions.bats and re-defined here so this file can run
# standalone).

# _apply_jq_flag <json_string> "$@"
# Scans positional args for "--jq FILTER", applies filter to json_string.
# If no --jq flag found, outputs json_string unchanged.
_apply_jq_flag() {
  local json="$1"; shift
  local filter=""
  while [[ $# -gt 0 ]]; do
    if [[ "$1" == "--jq" && $# -gt 1 ]]; then
      filter="$2"
      break
    fi
    shift
  done
  if [[ -n "$filter" ]]; then
    echo "$json" | jq -r "$filter"
  else
    echo "$json"
  fi
}
export -f _apply_jq_flag

_write_gh_stub() {
  local clean_sha="$CLEAN_SHA"

  # Build base64 payloads at stub-write time so the content is baked in.
  local dirty_b64
  dirty_b64=$(printf 'on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n      - uses: actions/setup-python@v5\n' | base64 -w0)

  local clean_b64
  clean_b64=$(printf 'on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@%s  # v4.0.0\n' "$clean_sha" | base64 -w0)

  cat > "$TEST_TMPDIR/bin/gh" <<STUB
#!/usr/bin/env bash

if [[ "\$1 \$2" == "auth status" ]]; then exit 0; fi

# gh repo list ORG --limit N --json name [--jq FILTER]
if [[ "\$1" == "repo" && "\$2" == "list" ]]; then
  _apply_jq_flag '[{"name":"repo-dirty"},{"name":"repo-clean"}]' "\$@"
  exit 0
fi

if [[ "\$1" == "api" ]]; then
  endpoint="\$2"

  # Directory listing: .github/workflows for repo-dirty
  if [[ "\$endpoint" == "repos/ByronWilliamsCPA/repo-dirty/contents/.github/workflows" ]]; then
    _apply_jq_flag '[{"name":"ci.yml","path":".github/workflows/ci.yml","type":"file"}]' "\$@"
    exit 0
  fi

  # Directory listing: .github/workflows for repo-clean
  if [[ "\$endpoint" == "repos/ByronWilliamsCPA/repo-clean/contents/.github/workflows" ]]; then
    _apply_jq_flag '[{"name":"ci.yml","path":".github/workflows/ci.yml","type":"file"}]' "\$@"
    exit 0
  fi

  # File content: ci.yml for repo-dirty (two tag-pinned third-party refs)
  if [[ "\$endpoint" == "repos/ByronWilliamsCPA/repo-dirty/contents/.github/workflows/ci.yml" ]]; then
    _apply_jq_flag '{"name":"ci.yml","encoding":"base64","content":"${dirty_b64}"}' "\$@"
    exit 0
  fi

  # File content: ci.yml for repo-clean (one SHA-pinned ref, no violations)
  if [[ "\$endpoint" == "repos/ByronWilliamsCPA/repo-clean/contents/.github/workflows/ci.yml" ]]; then
    _apply_jq_flag '{"name":"ci.yml","encoding":"base64","content":"${clean_b64}"}' "\$@"
    exit 0
  fi

  _apply_jq_flag '{}' "\$@"
  exit 0
fi

exit 0
STUB
  chmod +x "$TEST_TMPDIR/bin/gh"
}

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@test "audit reports dirty repo with two tag pins and clean repo as compliant" {
  _write_gh_stub
  run "$SCRIPT" --org ByronWilliamsCPA --output "$TEST_TMPDIR/out.csv"

  assert_success
  run cat "$TEST_TMPDIR/out.csv"
  assert_output --partial "ByronWilliamsCPA/repo-dirty,2"
  assert_output --partial "ByronWilliamsCPA/repo-clean,0"
}

@test "audit exits 0 even when violations are present (report-only)" {
  _write_gh_stub
  run "$SCRIPT" --org ByronWilliamsCPA --output "$TEST_TMPDIR/out.csv"
  assert_success
}
