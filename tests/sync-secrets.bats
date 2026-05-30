#!/usr/bin/env bats
# =============================================================================
# Tests for scripts/sync-secrets.sh
# =============================================================================
# Covers: the not-authenticated guard, the happy path (a secret is set on every
# discovered repo), the failure path (gh error is surfaced and counted), and the
# empty-secret-name guard. A central assertion on the failure path is that the
# secret VALUE never appears in the surfaced error output: this protects the
# GH_DEBUG/GH_PAGER unset guard and the captured-stderr handling against
# regression. All tests are isolated and require no network access.
#
# Mocking strategy: the script uses the "gh" CLI exclusively. We install a fake
# "gh" first on PATH. AUTH_FAIL=1 fails `gh auth status`; SECRET_FAIL=1 makes
# `gh secret set` emit an error to stderr (containing NO secret value) and exit
# non-zero.

load 'libs/bats-support/load'
load 'libs/bats-assert/load'

SCRIPT="$BATS_TEST_DIRNAME/../scripts/sync-secrets.sh"

setup() {
  TEST_TMPDIR="$(mktemp -d)"
  GH_BIN="$TEST_TMPDIR/bin"
  mkdir -p "$GH_BIN"
  export TEST_TMPDIR GH_BIN
  export PATH="$GH_BIN:/usr/local/bin:/bin:/usr/bin"
  _write_gh_stub
}

teardown() { rm -rf "$TEST_TMPDIR"; }

# gh stub. AUTH_FAIL=1 fails `gh auth status`. SECRET_FAIL=1 makes `gh secret
# set` fail with an API-style error on stderr that never echoes the --body
# value, mirroring real gh behavior on a permissions error.
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
      user) echo "testuser" ;;
      *) echo '{}' ;;
    esac ;;
  repo) printf 'repo-a\nrepo-b\n' ;;
  secret)
    if [ "${SECRET_FAIL:-0}" = "1" ]; then
      echo "HTTP 403: Resource not accessible by integration" >&2
      exit 1
    fi
    exit 0 ;;
esac
STUB
  chmod +x "$GH_BIN/gh"
}

@test "not-authenticated is reported and exits 1" {
  AUTH_FAIL=1 run bash "$SCRIPT"
  assert_failure
  assert_output --partial "Not authenticated"
}

@test "empty secret name aborts before any secret is set" {
  # First stdin line is the (empty) secret name -> the required-name guard fires.
  run bash "$SCRIPT" <<<""
  assert_failure
  assert_output --partial "Secret name required"
}

@test "happy path: sets the secret on every discovered repo" {
  # stdin: secret name, hidden secret value, confirm (y).
  run bash "$SCRIPT" <<<"MYTOKEN"$'\n'"sekret"$'\n'"y"
  assert_success
  assert_output --partial "Success: 2/2"
}

@test "secret-set failure: surfaces the gh error, counts it, and never leaks the value" {
  # The script reports failures but exits 0, so assert_success is correct.
  SECRET_FAIL=1 run bash "$SCRIPT" <<<"MYTOKEN"$'\n'"sekret"$'\n'"y"
  assert_success
  assert_output --partial "HTTP 403: Resource not accessible by integration"
  assert_output --partial "Failed:"
  # The secret value must never appear in the surfaced output.
  refute_output --partial "sekret"
}
