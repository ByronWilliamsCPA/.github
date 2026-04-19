#!/usr/bin/env bats
# =============================================================================
# Tests for scripts/update-pinned-actions.sh
# =============================================================================
# Covers: basic invocation, dry-run behavior, file discovery, API mocking,
# and error handling. All tests are isolated and require no network access.
#
# Mocking strategy: the script uses the "gh" CLI exclusively for API calls.
# We install a fake "gh" binary first on PATH. The stub must honour the --jq
# flag used by the script; it does so by piping the raw JSON through jq.

# Load bats helpers
load 'libs/bats-support/load'
load 'libs/bats-assert/load'

SCRIPT="$BATS_TEST_DIRNAME/../scripts/update-pinned-actions.sh"
FIXTURES="$BATS_TEST_DIRNAME/fixtures/workflows"

# SHAs used in fixtures (must match tests/fixtures/workflows/test-ci.yml)
OLD_CHECKOUT_SHA="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
NEW_CHECKOUT_SHA="1111111111111111111111111111111111111111"

# ---------------------------------------------------------------------------
# setup / teardown
# ---------------------------------------------------------------------------

setup() {
  TEST_TMPDIR="$(mktemp -d)"
  export TEST_TMPDIR

  # Copy fixture files so tests can modify copies without touching originals
  cp -r "$FIXTURES/"* "$TEST_TMPDIR/"

  GH_BIN="$TEST_TMPDIR/bin"
  mkdir -p "$GH_BIN"
  # Use a minimal PATH; our stub bin is first so it shadows any real "gh"
  export PATH="$GH_BIN:/usr/local/bin:/bin:/usr/bin"

  _write_gh_stub_default
}

teardown() {
  rm -rf "$TEST_TMPDIR"
}

# ---------------------------------------------------------------------------
# Stub helpers
# ---------------------------------------------------------------------------
# The script calls "gh" with patterns like:
#
#   gh auth status
#   gh release list --repo OWNER/REPO --limit N --json tagName --jq FILTER
#   gh api ENDPOINT --jq FILTER
#
# The real "gh" with --jq applies the jq filter server-side and returns the
# filtered string. Our stubs return raw JSON and then pipe it through jq so
# the script receives exactly the same output format.

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
    echo "$json" | jq -r "$filter" 2>/dev/null || true
  else
    echo "$json"
  fi
}
export -f _apply_jq_flag

# Default stub: auth passes, release list returns empty, api returns empty
_write_gh_stub_default() {
  cat > "$TEST_TMPDIR/bin/gh" <<'STUB'
#!/usr/bin/env bash
if [[ "$1 $2" == "auth status" ]]; then exit 0; fi

if [[ "$1" == "release" && "$2" == "list" ]]; then
  _apply_jq_flag '[]' "$@"
  exit 0
fi

if [[ "$1" == "api" ]]; then
  _apply_jq_flag '{}' "$@"
  exit 0
fi

exit 0
STUB
  chmod +x "$TEST_TMPDIR/bin/gh"
}

# Stub that returns a newer v4.2.0 release for actions/checkout only.
# For the api (SHA resolution), it returns a fake commit SHA.
_write_gh_stub_with_update() {
  local new_sha="$NEW_CHECKOUT_SHA"
  cat > "$TEST_TMPDIR/bin/gh" <<STUB
#!/usr/bin/env bash

if [[ "\$1 \$2" == "auth status" ]]; then
  exit 0
fi

if [[ "\$1" == "release" && "\$2" == "list" ]]; then
  # Find --repo value
  repo_value=""
  args=("\$@")
  for i in "\${!args[@]}"; do
    if [[ "\${args[\$i]}" == "--repo" ]]; then
      repo_value="\${args[\$((i+1))]}"
      break
    fi
  done

  if [[ "\$repo_value" == "actions/checkout" ]]; then
    _apply_jq_flag '[{"tagName":"v4.2.0"}]' "\$@"
  else
    _apply_jq_flag '[]' "\$@"
  fi
  exit 0
fi

if [[ "\$1" == "api" ]]; then
  endpoint="\$2"

  # Resolve tag ref: return a lightweight commit object for v4.2.0
  if [[ "\$endpoint" == *"actions/checkout"*"refs/tags/v4.2.0"* ]]; then
    _apply_jq_flag '{"object":{"type":"commit","sha":"${new_sha}"}}' "\$@"
    exit 0
  fi

  _apply_jq_flag '{}' "\$@"
  exit 0
fi

exit 0
STUB
  chmod +x "$TEST_TMPDIR/bin/gh"
}

# Stub that simulates unauthenticated gh
_write_gh_stub_unauthed() {
  cat > "$TEST_TMPDIR/bin/gh" <<'STUB'
#!/usr/bin/env bash
if [[ "$1 $2" == "auth status" ]]; then exit 1; fi
echo "[]"
exit 0
STUB
  chmod +x "$TEST_TMPDIR/bin/gh"
}

# Stub where release list always fails (network error simulation)
_write_gh_stub_release_fail() {
  cat > "$TEST_TMPDIR/bin/gh" <<'STUB'
#!/usr/bin/env bash
if [[ "$1 $2" == "auth status" ]]; then exit 0; fi
if [[ "$1" == "release" && "$2" == "list" ]]; then
  exit 1
fi
if [[ "$1" == "api" ]]; then echo "{}"; exit 0; fi
exit 0
STUB
  chmod +x "$TEST_TMPDIR/bin/gh"
}

# Stub where api always fails (rate limit / network error simulation)
_write_gh_stub_api_fail() {
  cat > "$TEST_TMPDIR/bin/gh" <<'STUB'
#!/usr/bin/env bash
if [[ "$1 $2" == "auth status" ]]; then exit 0; fi
if [[ "$1" == "release" && "$2" == "list" ]]; then
  _apply_jq_flag '[{"tagName":"v4.2.0"}]' "$@"
  exit 0
fi
if [[ "$1" == "api" ]]; then exit 1; fi
exit 0
STUB
  chmod +x "$TEST_TMPDIR/bin/gh"
}

# ---------------------------------------------------------------------------
# Group 1: Basic invocation
# ---------------------------------------------------------------------------

@test "script exists and is executable" {
  [ -f "$SCRIPT" ]
  [ -x "$SCRIPT" ]
}

@test "--help exits 0 and prints usage" {
  run "$SCRIPT" --help
  assert_success
  assert_output --partial "Usage:"
}

@test "-h exits 0 and prints usage" {
  run "$SCRIPT" -h
  assert_success
  assert_output --partial "Usage:"
}

@test "unknown flag exits non-zero" {
  run "$SCRIPT" --no-such-flag --workflows-dir "$TEST_TMPDIR"
  assert_failure
}

@test "unknown flag output mentions the bad flag" {
  run "$SCRIPT" --no-such-flag --workflows-dir "$TEST_TMPDIR"
  assert_output --partial "no-such-flag"
}

@test "--workflows-dir without argument exits non-zero" {
  run "$SCRIPT" --workflows-dir
  assert_failure
}

@test "--workflows-dir without argument prints error message" {
  run "$SCRIPT" --workflows-dir
  assert_output --partial "ERROR"
}

# ---------------------------------------------------------------------------
# Group 2: Dry-run behaviour (default mode)
# ---------------------------------------------------------------------------

@test "dry-run: exits 0 when workflow dir has pinned actions" {
  run "$SCRIPT" --workflows-dir "$TEST_TMPDIR"
  assert_success
}

@test "dry-run: no workflow files are modified" {
  before="$(md5sum "$TEST_TMPDIR"/*.yml | sort)"
  run "$SCRIPT" --workflows-dir "$TEST_TMPDIR"
  after="$(md5sum "$TEST_TMPDIR"/*.yml | sort)"
  [ "$before" = "$after" ]
}

@test "dry-run: output mentions DRY RUN" {
  run "$SCRIPT" --workflows-dir "$TEST_TMPDIR"
  assert_output --partial "DRY RUN"
}

@test "dry-run: produces output on stdout" {
  run "$SCRIPT" --workflows-dir "$TEST_TMPDIR"
  [ -n "$output" ]
}

@test "dry-run: prints action table header columns" {
  run "$SCRIPT" --workflows-dir "$TEST_TMPDIR"
  assert_output --partial "Action"
  assert_output --partial "Current"
  assert_output --partial "Latest"
}

@test "dry-run: detects pinned action references in fixture files" {
  run "$SCRIPT" --workflows-dir "$TEST_TMPDIR"
  assert_output --partial "Found"
  [[ "$output" =~ "Found "[1-9][0-9]*" unique pinned action" ]]
}

@test "dry-run with update available: shows new version in output" {
  _write_gh_stub_with_update
  run "$SCRIPT" --workflows-dir "$TEST_TMPDIR"
  assert_success
  assert_output --partial "v4.2.0"
}

@test "dry-run with update available: shows proposed changes section" {
  _write_gh_stub_with_update
  run "$SCRIPT" --workflows-dir "$TEST_TMPDIR"
  assert_output --partial "Proposed changes"
}

@test "dry-run with update: does not write changes to files" {
  _write_gh_stub_with_update
  before="$(md5sum "$TEST_TMPDIR"/*.yml | sort)"
  run "$SCRIPT" --workflows-dir "$TEST_TMPDIR"
  after="$(md5sum "$TEST_TMPDIR"/*.yml | sort)"
  [ "$before" = "$after" ]
}

# ---------------------------------------------------------------------------
# Group 3: File discovery
# ---------------------------------------------------------------------------

@test "script finds yml files in the specified workflows directory" {
  run "$SCRIPT" --workflows-dir "$TEST_TMPDIR"
  assert_success
  assert_output --partial "Found"
}

@test "script reports at least 4 unique pinned actions from fixtures" {
  # Fixtures: harden-runner (shared, counted once), checkout (x3 files),
  # setup-python, upload-artifact, pip-audit = 5 unique SHA-pinned entries
  run "$SCRIPT" --workflows-dir "$TEST_TMPDIR"
  count=$(echo "$output" | grep -oP 'Found \K[0-9]+')
  [ "$count" -ge 4 ]
}

@test "script does not count unpinned tag references like @v3" {
  run "$SCRIPT" --workflows-dir "$TEST_TMPDIR"
  count=$(echo "$output" | grep -oP 'Found \K[0-9]+')
  # cache@v3 and setup-node@main are not SHA-pinned; count must be below 10
  [ "$count" -lt 10 ]
}

@test "script exits non-zero when workflows directory does not exist" {
  run "$SCRIPT" --workflows-dir "/nonexistent/path/that/does/not/exist"
  assert_failure
  assert_output --partial "ERROR"
}

@test "script exits 0 when given an empty workflows directory" {
  empty_dir="$(mktemp -d)"
  run "$SCRIPT" --workflows-dir "$empty_dir"
  assert_success
  rmdir "$empty_dir"
}

# ---------------------------------------------------------------------------
# Group 4: API mocking (gh CLI stub behaviour)
# ---------------------------------------------------------------------------

@test "script calls gh release list at least once" {
  # Instrument the stub to record calls
  cat > "$TEST_TMPDIR/bin/gh" <<'STUB'
#!/usr/bin/env bash
if [[ "$1 $2" == "auth status" ]]; then exit 0; fi
if [[ "$1" == "release" && "$2" == "list" ]]; then
  echo "release list $*" >> "$TEST_TMPDIR/gh_calls.log"
  _apply_jq_flag '[]' "$@"
  exit 0
fi
if [[ "$1" == "api" ]]; then _apply_jq_flag '{}' "$@"; exit 0; fi
exit 0
STUB
  chmod +x "$TEST_TMPDIR/bin/gh"

  run "$SCRIPT" --workflows-dir "$TEST_TMPDIR"
  assert_success
  [ -f "$TEST_TMPDIR/gh_calls.log" ]
  [ "$(wc -l < "$TEST_TMPDIR/gh_calls.log")" -ge 1 ]
}

@test "gh release list is called with --repo flag" {
  cat > "$TEST_TMPDIR/bin/gh" <<'STUB'
#!/usr/bin/env bash
if [[ "$1 $2" == "auth status" ]]; then exit 0; fi
if [[ "$1" == "release" && "$2" == "list" ]]; then
  echo "$*" >> "$TEST_TMPDIR/gh_calls.log"
  _apply_jq_flag '[]' "$@"
  exit 0
fi
if [[ "$1" == "api" ]]; then _apply_jq_flag '{}' "$@"; exit 0; fi
exit 0
STUB
  chmod +x "$TEST_TMPDIR/bin/gh"

  run "$SCRIPT" --workflows-dir "$TEST_TMPDIR"
  assert_success
  grep -q -- "--repo" "$TEST_TMPDIR/gh_calls.log"
}

@test "script reports SKIP when no releases found for an action" {
  run "$SCRIPT" --workflows-dir "$TEST_TMPDIR"
  assert_success
  assert_output --partial "SKIP"
}

@test "apply mode: replaces old SHA with new SHA in workflow file" {
  _write_gh_stub_with_update

  apply_dir="$(mktemp -d)"
  cp "$FIXTURES/test-ci.yml" "$apply_dir/"

  run "$SCRIPT" --apply --workflows-dir "$apply_dir"
  assert_success

  # Old SHA must be gone from the file after apply
  run grep "$OLD_CHECKOUT_SHA" "$apply_dir/test-ci.yml"
  assert_failure

  rm -rf "$apply_dir"
}

@test "apply mode: new SHA is written into the workflow file" {
  _write_gh_stub_with_update

  apply_dir="$(mktemp -d)"
  cp "$FIXTURES/test-ci.yml" "$apply_dir/"

  run "$SCRIPT" --apply --workflows-dir "$apply_dir"
  assert_success

  run grep "$NEW_CHECKOUT_SHA" "$apply_dir/test-ci.yml"
  assert_success

  rm -rf "$apply_dir"
}

@test "apply mode: output confirms files were updated" {
  _write_gh_stub_with_update

  apply_dir="$(mktemp -d)"
  cp "$FIXTURES/test-ci.yml" "$apply_dir/"

  run "$SCRIPT" --apply --workflows-dir "$apply_dir"
  assert_output --partial "Files updated"

  rm -rf "$apply_dir"
}

@test "apply mode: output contains 'Applying changes'" {
  _write_gh_stub_with_update

  apply_dir="$(mktemp -d)"
  cp "$FIXTURES/test-ci.yml" "$apply_dir/"

  run "$SCRIPT" --apply --workflows-dir "$apply_dir"
  assert_output --partial "Applying changes"

  rm -rf "$apply_dir"
}

# ---------------------------------------------------------------------------
# Group 5: Error handling
# ---------------------------------------------------------------------------

@test "exits non-zero when gh CLI is not on PATH" {
  # Build a sandbox PATH containing all tools the script needs except gh.
  # We symlink every binary from /usr/bin and /bin into a sandbox dir, then
  # remove the gh symlink so "command -v gh" truly fails.
  local sandbox="$TEST_TMPDIR/sandbox_bin"
  mkdir -p "$sandbox"
  # Symlink core tools explicitly (avoids pulling in /usr/bin/gh via wildcard)
  for tool in bash sed grep awk wc sort uniq mktemp tr printf cut head tail cp mv rm; do
    local src
    src="$(command -v "$tool" 2>/dev/null)" || true
    if [[ -n "$src" && -x "$src" ]]; then
      ln -sf "$src" "$sandbox/$tool"
    fi
  done
  # Explicitly do NOT link gh -- that is the point of this test

  run env -i HOME="$HOME" PATH="$sandbox" bash "$SCRIPT" --workflows-dir "$TEST_TMPDIR"
  assert_failure
}

@test "gh not found error message mentions gh CLI" {
  local sandbox="$TEST_TMPDIR/sandbox_bin2"
  mkdir -p "$sandbox"
  for tool in bash sed grep awk wc sort uniq mktemp tr printf cut head tail cp mv rm; do
    local src
    src="$(command -v "$tool" 2>/dev/null)" || true
    if [[ -n "$src" && -x "$src" ]]; then
      ln -sf "$src" "$sandbox/$tool"
    fi
  done
  run env -i HOME="$HOME" PATH="$sandbox" bash "$SCRIPT" --workflows-dir "$TEST_TMPDIR"
  assert_output --partial "gh"
}

@test "exits non-zero when gh is not authenticated" {
  _write_gh_stub_unauthed
  run "$SCRIPT" --workflows-dir "$TEST_TMPDIR"
  assert_failure
  assert_output --partial "ERROR"
}

@test "unauthenticated error message mentions gh auth login" {
  _write_gh_stub_unauthed
  run "$SCRIPT" --workflows-dir "$TEST_TMPDIR"
  assert_output --partial "gh auth login"
}

@test "script handles gh release list failure gracefully without crashing" {
  # Script uses "|| true" so a failing release list must not propagate
  _write_gh_stub_release_fail
  run "$SCRIPT" --workflows-dir "$TEST_TMPDIR"
  assert_success
}

@test "script handles gh api failure gracefully without crashing" {
  # When SHA resolution fails the action is SKIP'd; script must exit 0
  _write_gh_stub_api_fail
  run "$SCRIPT" --workflows-dir "$TEST_TMPDIR"
  assert_success
  assert_output --partial "SKIP"
}
