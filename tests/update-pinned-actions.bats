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

# Prerequisite: run `git submodule update --init --recursive` before running
# these tests to populate tests/libs/bats-core, tests/libs/bats-support,
# and tests/libs/bats-assert.

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
    echo "$json" | jq -r "$filter"
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

  apply_dir="$TEST_TMPDIR/apply_workdir"
  mkdir -p "$apply_dir"
  cp "$FIXTURES/test-ci.yml" "$apply_dir/"

  run "$SCRIPT" --apply --workflows-dir "$apply_dir"
  assert_success

  # Old SHA must be gone from the file after apply
  run grep "$OLD_CHECKOUT_SHA" "$apply_dir/test-ci.yml"
  assert_failure

}

@test "apply mode: new SHA is written into the workflow file" {
  _write_gh_stub_with_update

  apply_dir="$TEST_TMPDIR/apply_workdir"
  mkdir -p "$apply_dir"
  cp "$FIXTURES/test-ci.yml" "$apply_dir/"

  run "$SCRIPT" --apply --workflows-dir "$apply_dir"
  assert_success

  run grep "$NEW_CHECKOUT_SHA" "$apply_dir/test-ci.yml"
  assert_success

}

@test "apply mode: output confirms files were updated" {
  _write_gh_stub_with_update

  apply_dir="$TEST_TMPDIR/apply_workdir"
  mkdir -p "$apply_dir"
  cp "$FIXTURES/test-ci.yml" "$apply_dir/"

  run "$SCRIPT" --apply --workflows-dir "$apply_dir"
  assert_output --partial "Files updated"

}

@test "apply mode: output contains 'Applying changes'" {
  _write_gh_stub_with_update

  apply_dir="$TEST_TMPDIR/apply_workdir"
  mkdir -p "$apply_dir"
  cp "$FIXTURES/test-ci.yml" "$apply_dir/"

  run "$SCRIPT" --apply --workflows-dir "$apply_dir"
  assert_output --partial "Applying changes"

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
  for tool in bash sed grep awk wc sort uniq mktemp tr printf cut head tail cp mv rm dirname; do
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
  for tool in bash sed grep awk wc sort uniq mktemp tr printf cut head tail cp mv rm dirname; do
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

# ---------------------------------------------------------------------------
# Group 6: Extended coverage (annotated tags, multi-file apply, no-op apply)
# ---------------------------------------------------------------------------

# Stub for annotated tag resolution.
# First API call (refs/tags) returns type=="tag" with an intermediate SHA.
# Second API call (git/tags/<sha>) dereferences to the final commit SHA.
_write_gh_stub_annotated_tag() {
  local annotated_sha="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
  local commit_sha="$NEW_CHECKOUT_SHA"
  cat > "$TEST_TMPDIR/bin/gh" <<STUB
#!/usr/bin/env bash

if [[ "\$1 \$2" == "auth status" ]]; then exit 0; fi

if [[ "\$1" == "release" && "\$2" == "list" ]]; then
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
  if [[ "\$endpoint" == *"refs/tags/v4.2.0"* ]]; then
    _apply_jq_flag '{"object":{"type":"tag","sha":"${annotated_sha}"}}' "\$@"
    exit 0
  fi
  if [[ "\$endpoint" == *"git/tags/"* ]]; then
    _apply_jq_flag '{"object":{"sha":"${commit_sha}"}}' "\$@"
    exit 0
  fi
  _apply_jq_flag '{}' "\$@"
  exit 0
fi

exit 0
STUB
  chmod +x "$TEST_TMPDIR/bin/gh"
}

@test "annotated tag: resolved commit SHA is written into the workflow file" {
  _write_gh_stub_annotated_tag

  apply_dir="$TEST_TMPDIR/apply_workdir"
  mkdir -p "$apply_dir"
  cp "$FIXTURES/test-ci.yml" "$apply_dir/"

  run "$SCRIPT" --apply --workflows-dir "$apply_dir"
  assert_success

  run grep "$NEW_CHECKOUT_SHA" "$apply_dir/test-ci.yml"
  assert_success
}

@test "apply mode: updates SHAs in multiple workflow files" {
  _write_gh_stub_with_update

  apply_dir="$TEST_TMPDIR/apply_workdir"
  mkdir -p "$apply_dir"
  cp "$FIXTURES/test-ci.yml" "$apply_dir/"
  cp "$FIXTURES/test-security.yml" "$apply_dir/"

  run "$SCRIPT" --apply --workflows-dir "$apply_dir"
  assert_success

  run grep "$NEW_CHECKOUT_SHA" "$apply_dir/test-ci.yml"
  assert_success
  run grep "$NEW_CHECKOUT_SHA" "$apply_dir/test-security.yml"
  assert_success
}

@test "apply mode: updated file contains version comment for new release" {
  _write_gh_stub_with_update

  apply_dir="$TEST_TMPDIR/apply_workdir"
  mkdir -p "$apply_dir"
  cp "$FIXTURES/test-ci.yml" "$apply_dir/"

  run "$SCRIPT" --apply --workflows-dir "$apply_dir"
  assert_success

  run grep "v4.2.0" "$apply_dir/test-ci.yml"
  assert_success
}

@test "apply mode: exit 0 and no 'Applying changes' when nothing to update" {
  # Default stub returns no releases, so there is nothing to update.

  apply_dir="$TEST_TMPDIR/apply_workdir"
  mkdir -p "$apply_dir"
  cp "$FIXTURES/test-ci.yml" "$apply_dir/"

  run "$SCRIPT" --apply --workflows-dir "$apply_dir"
  assert_success
  refute_output --partial "Applying changes"
}

# ---------------------------------------------------------------------------
# --pin-tags mode
# ---------------------------------------------------------------------------

# Fresh SHAs the gh stub returns for --pin-tags tests
CHECKOUT_V4_LATEST_TAG="v4.3.0"
CHECKOUT_V4_LATEST_SHA="8edcb1bdb4e267140fa742c62e395cd74f332709"  # pragma: allowlist secret
SETUP_PYTHON_V5_LATEST_TAG="v5.2.0"
SETUP_PYTHON_V5_LATEST_SHA="0b93645e9fea7318ecaed2b359559ac225c90a2b"  # pragma: allowlist secret

# Override the default gh stub to also answer tag-to-SHA resolution calls.
# Uses _apply_jq_flag (defined and exported above) so the stub honors --jq
# the same way the real gh CLI does, matching every other stub in this file.
_write_gh_stub_pin_tags() {
  cat > "$GH_BIN/gh" <<EOF
#!/usr/bin/env bash
set -e
case "\$*" in
  *"release list --repo actions/checkout"*)
    _apply_jq_flag '[{"tagName":"v4.3.0"},{"tagName":"v4.2.0"}]' "\$@" ;;
  *"release list --repo actions/setup-python"*)
    _apply_jq_flag '[{"tagName":"v5.2.0"},{"tagName":"v5.1.0"}]' "\$@" ;;
  *"actions/checkout"*"git/refs/tags/v4.3.0"*)
    _apply_jq_flag '{"object":{"type":"commit","sha":"$CHECKOUT_V4_LATEST_SHA"}}' "\$@" ;;
  *"actions/setup-python"*"git/refs/tags/v5.2.0"*)
    _apply_jq_flag '{"object":{"type":"commit","sha":"$SETUP_PYTHON_V5_LATEST_SHA"}}' "\$@" ;;
  *"auth status"*) exit 0 ;;
  *) echo "unexpected gh call: \$*" >&2; exit 1 ;;
esac
EOF
  chmod +x "$GH_BIN/gh"
}

@test "--pin-tags dry-run reports conversions without modifying files" {
  _write_gh_stub_pin_tags
  pin_tags_dir="$TEST_TMPDIR/pin_tags_workdir"
  mkdir -p "$pin_tags_dir"
  cp "$FIXTURES/tag-pinned.yml" "$pin_tags_dir/"

  run "$SCRIPT" --pin-tags --workflows-dir "$pin_tags_dir"

  assert_success
  assert_output --partial "actions/checkout@v4"
  assert_output --partial "$CHECKOUT_V4_LATEST_TAG"
  assert_output --partial "DRY RUN"
  # File unchanged
  run grep -F "actions/checkout@v4" "$pin_tags_dir/tag-pinned.yml"
  assert_success
}

@test "--pin-tags --apply rewrites tag refs to SHA with trailing comment" {
  _write_gh_stub_pin_tags
  pin_tags_dir="$TEST_TMPDIR/pin_tags_workdir"
  mkdir -p "$pin_tags_dir"
  cp "$FIXTURES/tag-pinned.yml" "$pin_tags_dir/"

  run "$SCRIPT" --pin-tags --apply --workflows-dir "$pin_tags_dir"

  assert_success
  run grep -F "actions/checkout@$CHECKOUT_V4_LATEST_SHA  # $CHECKOUT_V4_LATEST_TAG" \
    "$pin_tags_dir/tag-pinned.yml"
  assert_success
  run grep -F "actions/setup-python@$SETUP_PYTHON_V5_LATEST_SHA  # $SETUP_PYTHON_V5_LATEST_TAG" \
    "$pin_tags_dir/tag-pinned.yml"
  assert_success
}

@test "--pin-tags leaves first-party org refs untouched" {
  _write_gh_stub_pin_tags
  pin_tags_dir="$TEST_TMPDIR/pin_tags_workdir"
  mkdir -p "$pin_tags_dir"
  cp "$FIXTURES/tag-pinned.yml" "$pin_tags_dir/"

  run "$SCRIPT" --pin-tags --apply --workflows-dir "$pin_tags_dir"

  assert_success
  run grep -F "ByronWilliamsCPA/.github/.github/workflows/python-ci.yml@v1" \
    "$pin_tags_dir/tag-pinned.yml"
  assert_success
  run grep -F "williaby/.github/.github/workflows/release-tag.yml@v1" \
    "$pin_tags_dir/tag-pinned.yml"
  assert_success
}

@test "--pin-tags refuses to convert branch refs and reports them" {
  _write_gh_stub_pin_tags
  pin_tags_dir="$TEST_TMPDIR/pin_tags_workdir"
  mkdir -p "$pin_tags_dir"
  cp "$FIXTURES/tag-pinned.yml" "$pin_tags_dir/"

  run "$SCRIPT" --pin-tags --apply --workflows-dir "$pin_tags_dir"

  assert_success
  assert_output --partial "some-org/some-action@main"
  assert_output --partial "branch ref"
  # Branch ref left untouched
  run grep -F "some-org/some-action@main" "$pin_tags_dir/tag-pinned.yml"
  assert_success
}

@test "--pin-tags converts refs that already have an inline comment" {
  _write_gh_stub_pin_tags
  pin_tags_dir="$TEST_TMPDIR/pin_tags_workdir"
  mkdir -p "$pin_tags_dir"
  cat > "$pin_tags_dir/inline-comment.yml" <<'YML'
name: Fixture
on: push
jobs:
  example:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4  # using v4 stable
      - uses: actions/setup-python@v5
YML

  run "$SCRIPT" --pin-tags --apply --workflows-dir "$pin_tags_dir"
  assert_success
  # The trailing inline comment is dropped; new SHA + tag comment replaces it
  run grep -F "actions/checkout@$CHECKOUT_V4_LATEST_SHA  # $CHECKOUT_V4_LATEST_TAG" \
    "$pin_tags_dir/inline-comment.yml"
  assert_success
  # No remnant of the old "using v4 stable" comment
  run grep -F "using v4 stable" "$pin_tags_dir/inline-comment.yml"
  assert_failure
}

@test "--pin-tags honors a custom --owner-allowlist" {
  _write_gh_stub_pin_tags
  pin_tags_dir="$TEST_TMPDIR/pin_tags_workdir"
  mkdir -p "$pin_tags_dir"
  cp "$FIXTURES/tag-pinned.yml" "$pin_tags_dir/"

  # Add "actions" to the allowlist so actions/checkout becomes first-party
  run "$SCRIPT" --pin-tags --apply --owner-allowlist actions \
    --workflows-dir "$pin_tags_dir"
  assert_success

  # actions/checkout@v4 is now treated as first-party, so it stays as a tag ref
  run grep -F "actions/checkout@v4" "$pin_tags_dir/tag-pinned.yml"
  assert_success
  # actions/setup-python@v5 likewise untouched
  run grep -F "actions/setup-python@v5" "$pin_tags_dir/tag-pinned.yml"
  assert_success
}

# Stub for --pin-tags + annotated-tag dereferencing.
# Two-step resolution: refs/tags -> tag object SHA, then git/tags -> commit SHA.
_write_gh_stub_pin_tags_annotated() {
  local annotated_sha="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"  # pragma: allowlist secret
  local commit_sha="$CHECKOUT_V4_LATEST_SHA"
  cat > "$GH_BIN/gh" <<EOF
#!/usr/bin/env bash
set -e
case "\$*" in
  *"release list --repo actions/checkout"*)
    _apply_jq_flag '[{"tagName":"v4.3.0"}]' "\$@" ;;
  *"release list --repo actions/setup-python"*)
    _apply_jq_flag '[{"tagName":"v5.2.0"}]' "\$@" ;;
  *"actions/checkout"*"git/refs/tags/v4.3.0"*)
    _apply_jq_flag '{"object":{"type":"tag","sha":"${annotated_sha}"}}' "\$@" ;;
  *"actions/checkout"*"git/tags/${annotated_sha}"*)
    _apply_jq_flag '{"object":{"sha":"${commit_sha}"}}' "\$@" ;;
  *"actions/setup-python"*"git/refs/tags/v5.2.0"*)
    _apply_jq_flag '{"object":{"type":"commit","sha":"$SETUP_PYTHON_V5_LATEST_SHA"}}' "\$@" ;;
  *"auth status"*) exit 0 ;;
  *) echo "unexpected gh call: \$*" >&2; exit 1 ;;
esac
EOF
  chmod +x "$GH_BIN/gh"
}

@test "--pin-tags resolves annotated tags via two-step dereferencing" {
  _write_gh_stub_pin_tags_annotated
  pin_tags_dir="$TEST_TMPDIR/pin_tags_workdir"
  mkdir -p "$pin_tags_dir"
  cp "$FIXTURES/tag-pinned.yml" "$pin_tags_dir/"

  run "$SCRIPT" --pin-tags --apply --workflows-dir "$pin_tags_dir"
  assert_success

  # The dereferenced commit SHA must appear, not the intermediate tag-object SHA
  run grep -F "actions/checkout@$CHECKOUT_V4_LATEST_SHA  # $CHECKOUT_V4_LATEST_TAG" \
    "$pin_tags_dir/tag-pinned.yml"
  assert_success
  # The annotated tag-object SHA must NOT leak into the file
  run grep -F "@bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" \
    "$pin_tags_dir/tag-pinned.yml"
  assert_failure
}

@test "--pin-tags --apply preserves & and | literal in tag-name comment" {
  # Git ref naming permits & and | in tag names; both characters are sed
  # metacharacters (& expands the matched pattern in the replacement, |
  # is the sed delimiter used by this script). The safe_tag escape block
  # must keep them literal in the trailing comment, and escape_sed_pat
  # must keep current_tag from being interpreted as a regex if any tag
  # ever ships with these characters in its current pin.
  local SPECIAL_TAG='v4.5.0+amp&pipe|x'
  local SPECIAL_SHA='cccccccccccccccccccccccccccccccccccccccc'  # pragma: allowlist secret -- 40-char fixture, not a real SHA
  cat > "$GH_BIN/gh" <<EOF
#!/usr/bin/env bash
set -e
case "\$*" in
  *"release list --repo actions/checkout"*)
    _apply_jq_flag '[{"tagName":"$SPECIAL_TAG"}]' "\$@" ;;
  *"release list --repo actions/setup-python"*)
    _apply_jq_flag '[{"tagName":"v5.2.0"}]' "\$@" ;;
  *"actions/checkout"*"git/refs/tags/"*)
    _apply_jq_flag '{"object":{"type":"commit","sha":"$SPECIAL_SHA"}}' "\$@" ;;
  *"actions/setup-python"*"git/refs/tags/v5.2.0"*)
    _apply_jq_flag '{"object":{"type":"commit","sha":"$SETUP_PYTHON_V5_LATEST_SHA"}}' "\$@" ;;
  *"auth status"*) exit 0 ;;
  *) echo "unexpected gh call: \$*" >&2; exit 1 ;;
esac
EOF
  chmod +x "$GH_BIN/gh"

  pin_tags_dir="$TEST_TMPDIR/pin_tags_workdir"
  mkdir -p "$pin_tags_dir"
  cp "$FIXTURES/tag-pinned.yml" "$pin_tags_dir/"

  run "$SCRIPT" --pin-tags --apply --workflows-dir "$pin_tags_dir"
  assert_success

  # The literal special tag, including & and |, must appear verbatim in the
  # trailing comment. If safe_tag's escaping is removed, sed would expand &
  # to the matched ref or treat | as a field terminator.
  run grep -F "actions/checkout@$SPECIAL_SHA  # $SPECIAL_TAG" \
    "$pin_tags_dir/tag-pinned.yml"
  assert_success
}

@test "--pin-tags reports branch refs that carry an inline comment" {
  # extract_branch_pins was updated to accept "# comment" suffixes; the
  # existing branch-comment fixture (tag-pinned.yml's some-org/some-action@main)
  # has no comment, so this path is unverified. Add a fixture with a
  # comment-annotated branch ref and assert it surfaces in the WARN list.
  _write_gh_stub_pin_tags
  pin_tags_dir="$TEST_TMPDIR/pin_tags_workdir"
  mkdir -p "$pin_tags_dir"
  cat > "$pin_tags_dir/branch-with-comment.yml" <<'YML'
name: Fixture
on: push
jobs:
  example:
    runs-on: ubuntu-latest
    steps:
      - uses: some-org/branch-action@main  # tracking head
      - uses: actions/checkout@v4
YML

  run "$SCRIPT" --pin-tags --workflows-dir "$pin_tags_dir"
  assert_success
  # The branch ref must appear in the WARN block even though it carries
  # an inline "# tracking head" comment that the old regex would have
  # treated as the line terminator. Anchor the assertion to the WARN
  # header so a future regression that merely echoed the fixture name
  # or unrelated context can't pass this test silently.
  assert_output --partial "WARN: branch ref detected"
  assert_output --partial "some-org/branch-action@main"
}

@test "--pin-tags --apply on a workflow with no third-party refs succeeds without warnings" {
  # Regression guard for the rc-aware extract_tag_pins/extract_branch_pins
  # path: a fixture containing ONLY first-party refs (skipped by the
  # owner allowlist) means grep matches lines but the awk filter emits
  # nothing. The function must return 0 cleanly and the script must exit 0.
  _write_gh_stub_pin_tags
  pin_tags_dir="$TEST_TMPDIR/pin_tags_workdir"
  mkdir -p "$pin_tags_dir"
  cat > "$pin_tags_dir/all-first-party.yml" <<'YML'
name: Fixture
on: push
jobs:
  example:
    runs-on: ubuntu-latest
    steps:
      - uses: ByronWilliamsCPA/.github/.github/workflows/python-ci.yml@v1
      - uses: williaby/.github/.github/workflows/release-tag.yml@v1
YML

  run "$SCRIPT" --pin-tags --apply --workflows-dir "$pin_tags_dir"
  assert_success
  assert_output --partial "No third-party tag-pinned actions found"
  # First-party refs must be untouched
  run grep -F "ByronWilliamsCPA/.github/.github/workflows/python-ci.yml@v1" \
    "$pin_tags_dir/all-first-party.yml"
  assert_success
}

@test "--pin-tags --apply skips when annotated-tag dereferencing returns missing .object.sha" {
  # Stub the two-step dereferencing path so the second call returns an
  # object without `.sha`. jq emits "null" under -r; resolve_tag_sha must
  # detect that and return empty, causing the action to be marked SKIPPED
  # rather than writing "actions/checkout@null" into the workflow file.
  local annotated_sha="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"  # pragma: allowlist secret
  cat > "$GH_BIN/gh" <<EOF
#!/usr/bin/env bash
set -e
case "\$*" in
  *"release list --repo actions/checkout"*)
    _apply_jq_flag '[{"tagName":"v4.3.0"}]' "\$@" ;;
  *"release list --repo actions/setup-python"*)
    _apply_jq_flag '[{"tagName":"v5.2.0"}]' "\$@" ;;
  *"actions/checkout"*"git/refs/tags/v4.3.0"*)
    _apply_jq_flag '{"object":{"type":"tag","sha":"${annotated_sha}"}}' "\$@" ;;
  *"actions/checkout"*"git/tags/${annotated_sha}"*)
    # Malformed response: object present but no .sha field
    _apply_jq_flag '{"object":{}}' "\$@" ;;
  *"actions/setup-python"*"git/refs/tags/v5.2.0"*)
    _apply_jq_flag '{"object":{"type":"commit","sha":"$SETUP_PYTHON_V5_LATEST_SHA"}}' "\$@" ;;
  *"auth status"*) exit 0 ;;
  *) echo "unexpected gh call: \$*" >&2; exit 1 ;;
esac
EOF
  chmod +x "$GH_BIN/gh"

  pin_tags_dir="$TEST_TMPDIR/pin_tags_workdir"
  mkdir -p "$pin_tags_dir"
  cp "$FIXTURES/tag-pinned.yml" "$pin_tags_dir/"

  run "$SCRIPT" --pin-tags --apply --workflows-dir "$pin_tags_dir"
  assert_success
  assert_output --partial "SKIP: cannot resolve SHA"

  # The original v4 ref must remain untouched: the dereferencing failed,
  # so no substitution should have happened for actions/checkout.
  run grep -F "actions/checkout@v4" "$pin_tags_dir/tag-pinned.yml"
  assert_success
  # The literal string "null" must NOT have leaked into the workflow file
  run grep -F "actions/checkout@null" "$pin_tags_dir/tag-pinned.yml"
  assert_failure
  # actions/setup-python had a clean lightweight-tag path; it should be
  # converted normally
  run grep -F "actions/setup-python@$SETUP_PYTHON_V5_LATEST_SHA" \
    "$pin_tags_dir/tag-pinned.yml"
  assert_success
}

@test "--pin-tags --apply skips when first git/refs/tags call returns null .object.type" {
  # The Suggested-tier follow-up review noted only the SECOND-call null guard
  # was tested. This exercises the FIRST-call guard (added at
  # scripts/update-pinned-actions.sh:138): when the initial
  # `repos/$repo/git/refs/tags/$tag` response has a malformed `.object`
  # (e.g., `null`), jq -r emits the literal "null" for both fields and
  # `resolve_tag_sha` must mark the action SKIPPED rather than writing
  # `@null` into the workflow file. The stderr WARN added alongside the
  # guard must also fire so operators can distinguish malformed responses
  # from "tag does not exist".
  cat > "$GH_BIN/gh" <<EOF
#!/usr/bin/env bash
set -e
case "\$*" in
  *"release list --repo actions/checkout"*)
    _apply_jq_flag '[{"tagName":"v4.3.0"}]' "\$@" ;;
  *"release list --repo actions/setup-python"*)
    _apply_jq_flag '[{"tagName":"v5.2.0"}]' "\$@" ;;
  *"actions/checkout"*"git/refs/tags/v4.3.0"*)
    # Malformed: .object is null, so jq emits "null|null".
    _apply_jq_flag '{"object":null}' "\$@" ;;
  *"actions/setup-python"*"git/refs/tags/v5.2.0"*)
    _apply_jq_flag '{"object":{"type":"commit","sha":"$SETUP_PYTHON_V5_LATEST_SHA"}}' "\$@" ;;
  *"auth status"*) exit 0 ;;
  *) echo "unexpected gh call: \$*" >&2; exit 1 ;;
esac
EOF
  chmod +x "$GH_BIN/gh"

  pin_tags_dir="$TEST_TMPDIR/pin_tags_workdir"
  mkdir -p "$pin_tags_dir"
  cp "$FIXTURES/tag-pinned.yml" "$pin_tags_dir/"

  run "$SCRIPT" --pin-tags --apply --workflows-dir "$pin_tags_dir"
  assert_success
  assert_output --partial "SKIP: cannot resolve SHA"
  # The new WARN must fire on the first-call null-object path.
  assert_output --partial "null/empty .object.type or .object.sha"

  # actions/checkout was malformed: original v4 ref must remain.
  run grep -F "actions/checkout@v4" "$pin_tags_dir/tag-pinned.yml"
  assert_success
  # The literal string "null" must NOT have leaked into the workflow file.
  run grep -F "actions/checkout@null" "$pin_tags_dir/tag-pinned.yml"
  assert_failure
  # actions/setup-python had a clean lightweight-tag path; converted normally.
  run grep -F "actions/setup-python@$SETUP_PYTHON_V5_LATEST_SHA" \
    "$pin_tags_dir/tag-pinned.yml"
  assert_success
}
