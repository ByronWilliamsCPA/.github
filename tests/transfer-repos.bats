#!/usr/bin/env bats
# =============================================================================
# Tests for scripts/transfer-repos.sh
# =============================================================================
# Covers: argument parsing (--help, unknown args), the not-authenticated
# guard, and the --dry-run path (lists repositories, performs no transfer).
# All tests are isolated and require no network access.
#
# Mocking strategy: the script uses the "gh" CLI exclusively. We install a
# fake "gh" binary first on PATH. The stub records a marker file if the
# transfer endpoint is ever called, so dry-run can assert no transfer fired.

load 'libs/bats-support/load'
load 'libs/bats-assert/load'

SCRIPT="$BATS_TEST_DIRNAME/../scripts/transfer-repos.sh"

setup() {
  TEST_TMPDIR="$(mktemp -d)"
  GH_BIN="$TEST_TMPDIR/bin"
  mkdir -p "$GH_BIN"
  MARKER="$TEST_TMPDIR/transfer_called"
  export TEST_TMPDIR MARKER GH_BIN
  export PATH="$GH_BIN:/usr/local/bin:/bin:/usr/bin"
  _write_gh_stub
}

teardown() { rm -rf "$TEST_TMPDIR"; }

# gh stub. AUTH_FAIL=1 makes `gh auth status` fail. TRANSFER_FAIL=1 makes the
# transfer endpoint emit an API error to stderr and exit non-zero so the
# error-surfacing branch runs. On the success path the transfer endpoint
# touches $MARKER so tests can prove whether a transfer was attempted.
_write_gh_stub() {
  cat > "$GH_BIN/gh" <<'STUB'
#!/usr/bin/env bash
case "$1" in
  auth)
    if [ "${AUTH_FAIL:-0}" = "1" ]; then exit 1; fi
    exit 0 ;;
  api)
    shift
    case "$1" in
      user/orgs) echo "  - testorg" ;;
      user) echo "testuser" ;;
      orgs/*) exit 0 ;;
      repos/*/transfer)
        if [ "${TRANSFER_FAIL:-0}" = "1" ]; then
          echo "API error: Must be an organization owner" >&2
          exit 1
        fi
        : > "${MARKER:?}"; echo '{}'; exit 0 ;;
      repos/*) echo '{}'; exit 0 ;;
      *) echo '{}' ;;
    esac ;;
  repo) printf 'repo-a\nrepo-b\n' ;;
esac
STUB
  chmod +x "$GH_BIN/gh"
}

@test "--help prints usage and exits 0" {
  run bash "$SCRIPT" --help
  assert_success
  assert_output --partial "Usage:"
  assert_output --partial "--dry-run"
}

@test "unknown argument exits non-zero" {
  run bash "$SCRIPT" --bogus
  assert_failure
  assert_output --partial "Unknown argument"
}

@test "not-authenticated is reported and exits 1" {
  AUTH_FAIL=1 run bash "$SCRIPT"
  assert_failure
  assert_output --partial "Not authenticated"
}

@test "--dry-run lists repositories and transfers nothing" {
  run bash "$SCRIPT" --dry-run <<<"testorg"
  assert_success
  assert_output --partial "Dry run enabled"
  assert_output --partial "repo-a"
  assert_output --partial "repo-b"
  [ ! -e "$MARKER" ]
}

@test "transfer failure: surfaces the gh API error and counts it failed" {
  # stdin drives two prompts: the target org name, then confirm-all (y).
  # TRANSFER_FAIL forces the transfer endpoint to fail so the error-surfacing
  # branch added in this PR runs. The script reports failures but exits 0, so
  # assert_success is correct here; the regression guarded against is a revert
  # to discarding gh stderr (the previous `&>/dev/null`).
  TRANSFER_FAIL=1 run bash "$SCRIPT" <<<"testorg"$'\n'"y"
  assert_success
  assert_output --partial "API error: Must be an organization owner"
  assert_output --partial "Failed:"
}
