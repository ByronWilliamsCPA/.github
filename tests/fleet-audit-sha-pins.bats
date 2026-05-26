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

@test "audit emits 'error' sentinel when API call fails (not 404)" {
  # Stub returns the repo list, then fails every contents API with a 429
  cat > "$TEST_TMPDIR/bin/gh" <<'STUB'
#!/usr/bin/env bash
if [[ "$1 $2" == "auth status" ]]; then exit 0; fi
if [[ "$1" == "repo" && "$2" == "list" ]]; then
  _apply_jq_flag '[{"name":"repo-rate-limited"}]' "$@"
  exit 0
fi
if [[ "$1" == "api" ]]; then
  echo "gh: API rate limit exceeded for user (HTTP 429)" >&2
  exit 1
fi
exit 0
STUB
  chmod +x "$TEST_TMPDIR/bin/gh"

  run "$SCRIPT" --org ByronWilliamsCPA --output "$TEST_TMPDIR/out.csv"
  assert_success   # script remains report-only; non-zero would block runs

  run cat "$TEST_TMPDIR/out.csv"
  assert_output --partial "ByronWilliamsCPA/repo-rate-limited,error"
}

@test "audit treats 404 on workflows directory as a legitimate zero" {
  # Stub returns the repo list, then a 404 for the workflows directory
  cat > "$TEST_TMPDIR/bin/gh" <<'STUB'
#!/usr/bin/env bash
if [[ "$1 $2" == "auth status" ]]; then exit 0; fi
if [[ "$1" == "repo" && "$2" == "list" ]]; then
  _apply_jq_flag '[{"name":"repo-no-workflows"}]' "$@"
  exit 0
fi
if [[ "$1" == "api" ]]; then
  echo "gh: Not Found (HTTP 404)" >&2
  exit 1
fi
exit 0
STUB
  chmod +x "$TEST_TMPDIR/bin/gh"

  run "$SCRIPT" --org ByronWilliamsCPA --output "$TEST_TMPDIR/out.csv"
  assert_success

  run cat "$TEST_TMPDIR/out.csv"
  assert_output --partial "ByronWilliamsCPA/repo-no-workflows,0"
  refute_output --partial "ByronWilliamsCPA/repo-no-workflows,error"
}

@test "audit --skip-owners with regex metacharacters does not silently skip violations" {
  # Under the legacy regex-based skip check, --skip-owners '.*' would have
  # matched every owner and silently zeroed all violations. The literal
  # case-match in is_skipped_owner must treat '.*' as a literal owner name
  # (which no GitHub account is named) and still count the two violations
  # in repo-dirty.
  _write_gh_stub
  run "$SCRIPT" --org ByronWilliamsCPA --skip-owners '.*' --output "$TEST_TMPDIR/out.csv"
  assert_success

  run cat "$TEST_TMPDIR/out.csv"
  assert_output --partial "ByronWilliamsCPA/repo-dirty,2"
  refute_output --partial "ByronWilliamsCPA/repo-dirty,0"
}

@test "audit emits 'error' sentinel when one file fetches OK and another fails (mixed success)" {
  # The workflows listing succeeds with two files; the first content fetch
  # returns a violation, the second returns 429. The api_error flag must
  # propagate so the repo row is 'error', not a misleading partial count.
  local dirty_b64
  dirty_b64=$(printf 'on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n' | base64 -w0)

  cat > "$TEST_TMPDIR/bin/gh" <<STUB
#!/usr/bin/env bash
if [[ "\$1 \$2" == "auth status" ]]; then exit 0; fi
if [[ "\$1" == "repo" && "\$2" == "list" ]]; then
  _apply_jq_flag '[{"name":"repo-partial-fail"}]' "\$@"
  exit 0
fi
if [[ "\$1" == "api" ]]; then
  endpoint="\$2"
  if [[ "\$endpoint" == "repos/ByronWilliamsCPA/repo-partial-fail/contents/.github/workflows" ]]; then
    _apply_jq_flag '[{"name":"a.yml","path":".github/workflows/a.yml","type":"file"},{"name":"b.yml","path":".github/workflows/b.yml","type":"file"}]' "\$@"
    exit 0
  fi
  if [[ "\$endpoint" == "repos/ByronWilliamsCPA/repo-partial-fail/contents/.github/workflows/a.yml" ]]; then
    _apply_jq_flag '{"name":"a.yml","encoding":"base64","content":"${dirty_b64}"}' "\$@"
    exit 0
  fi
  if [[ "\$endpoint" == "repos/ByronWilliamsCPA/repo-partial-fail/contents/.github/workflows/b.yml" ]]; then
    echo "gh: API rate limit exceeded for user (HTTP 429)" >&2
    exit 1
  fi
fi
exit 0
STUB
  chmod +x "$TEST_TMPDIR/bin/gh"

  run "$SCRIPT" --org ByronWilliamsCPA --output "$TEST_TMPDIR/out.csv"
  assert_success

  run cat "$TEST_TMPDIR/out.csv"
  assert_output --partial "ByronWilliamsCPA/repo-partial-fail,error"
  refute_output --partial "ByronWilliamsCPA/repo-partial-fail,1"
}

@test "audit warns when gh repo list saturates REPO_LIMIT" {
  # REPO_LIMIT is env-overridable. Stub returns exactly 3 repos and the test
  # sets REPO_LIMIT=3; the script must emit a stderr WARN that this run may
  # be truncated. Without the env override, exercising this WARN required
  # arranging a 1000-repo stub.
  cat > "$TEST_TMPDIR/bin/gh" <<'STUB'
#!/usr/bin/env bash
if [[ "$1 $2" == "auth status" ]]; then exit 0; fi
if [[ "$1" == "repo" && "$2" == "list" ]]; then
  _apply_jq_flag '[{"name":"a"},{"name":"b"},{"name":"c"}]' "$@"
  exit 0
fi
if [[ "$1" == "api" ]]; then
  # 404 on contents/.github/workflows so each repo records 0 cleanly
  echo "gh: Not Found (HTTP 404)" >&2
  exit 1
fi
exit 0
STUB
  chmod +x "$TEST_TMPDIR/bin/gh"

  REPO_LIMIT=3 run "$SCRIPT" --org ByronWilliamsCPA --output "$TEST_TMPDIR/out.csv"
  assert_success
  assert_output --partial "WARN: ByronWilliamsCPA returned exactly 3 repos"
}

@test "audit STRICT_AUDIT=1 exits non-zero on REPO_LIMIT saturation" {
  cat > "$TEST_TMPDIR/bin/gh" <<'STUB'
#!/usr/bin/env bash
if [[ "$1 $2" == "auth status" ]]; then exit 0; fi
if [[ "$1" == "repo" && "$2" == "list" ]]; then
  _apply_jq_flag '[{"name":"a"},{"name":"b"}]' "$@"
  exit 0
fi
if [[ "$1" == "api" ]]; then
  echo "gh: Not Found (HTTP 404)" >&2
  exit 1
fi
exit 0
STUB
  chmod +x "$TEST_TMPDIR/bin/gh"

  REPO_LIMIT=2 STRICT_AUDIT=1 run "$SCRIPT" --org ByronWilliamsCPA --output "$TEST_TMPDIR/out.csv"
  # Script exits 2 to distinguish "audit incomplete" from a generic error
  [[ "$status" -eq 2 ]] || { echo "expected exit 2 under STRICT_AUDIT, got $status"; return 1; }
  assert_output --partial "ERROR: STRICT_AUDIT=1 and the audit was incomplete"
}

@test "audit STRICT_AUDIT=1 exits non-zero when any repo emits error sentinel" {
  cat > "$TEST_TMPDIR/bin/gh" <<'STUB'
#!/usr/bin/env bash
if [[ "$1 $2" == "auth status" ]]; then exit 0; fi
if [[ "$1" == "repo" && "$2" == "list" ]]; then
  _apply_jq_flag '[{"name":"repo-down"}]' "$@"
  exit 0
fi
if [[ "$1" == "api" ]]; then
  echo "gh: API rate limit exceeded for user (HTTP 429)" >&2
  exit 1
fi
exit 0
STUB
  chmod +x "$TEST_TMPDIR/bin/gh"

  STRICT_AUDIT=1 run "$SCRIPT" --org ByronWilliamsCPA --output "$TEST_TMPDIR/out.csv"
  [[ "$status" -eq 2 ]] || { echo "expected exit 2 under STRICT_AUDIT, got $status"; return 1; }
  assert_output --partial "ERROR: STRICT_AUDIT=1 and the audit was incomplete"
  run cat "$TEST_TMPDIR/out.csv"
  assert_output --partial "ByronWilliamsCPA/repo-down,error"
}

@test "audit STRICT_AUDIT=1 remains exit 0 on a fully clean run (no errors, no saturation)" {
  # Regression guard: a clean run under STRICT_AUDIT must still succeed.
  # Otherwise CI gates would fire on every healthy audit.
  _write_gh_stub
  STRICT_AUDIT=1 run "$SCRIPT" --org ByronWilliamsCPA --output "$TEST_TMPDIR/out.csv"
  assert_success
  run cat "$TEST_TMPDIR/out.csv"
  assert_output --partial "ByronWilliamsCPA/repo-dirty,2"
  assert_output --partial "ByronWilliamsCPA/repo-clean,0"
}

@test "audit --skip-owners with a single owner (no commas) skips correctly" {
  # SKIP_OWNERS framing is ",$VAR," so a single value becomes ",actions,"
  # and matches an owner literally named "actions". Verifies the case
  # statement handles the no-comma input.
  _write_gh_stub
  run "$SCRIPT" --org ByronWilliamsCPA --skip-owners 'actions' --output "$TEST_TMPDIR/out.csv"
  assert_success
  run cat "$TEST_TMPDIR/out.csv"
  # repo-dirty has two third-party actions/* refs; both should now be skipped
  assert_output --partial "ByronWilliamsCPA/repo-dirty,0"
}

@test "audit --skip-owners with empty string does not skip anything" {
  # Empty SKIP_OWNERS becomes the case pattern ",,". No real owner string
  # matches that, so both violations in repo-dirty must still be counted.
  _write_gh_stub
  run "$SCRIPT" --org ByronWilliamsCPA --skip-owners '' --output "$TEST_TMPDIR/out.csv"
  assert_success
  run cat "$TEST_TMPDIR/out.csv"
  assert_output --partial "ByronWilliamsCPA/repo-dirty,2"
}

@test "audit --skip-owners with double internal commas still matches listed owners" {
  # SKIP_OWNERS=",,actions,," builds the case framing ",,,actions,,," which
  # contains noisy empty segments. Owner "actions" must still match the
  # ",actions," substring without confusion from the adjacent empties.
  # Both refs in repo-dirty (actions/checkout, actions/setup-python) share
  # owner "actions" and should both be skipped.
  _write_gh_stub
  run "$SCRIPT" --org ByronWilliamsCPA --skip-owners ',,actions,,' \
    --output "$TEST_TMPDIR/out.csv"
  assert_success
  run cat "$TEST_TMPDIR/out.csv"
  assert_output --partial "ByronWilliamsCPA/repo-dirty,0"
}
