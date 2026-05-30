#!/usr/bin/env bats
# =============================================================================
# Tests for sync_org_files.sh
# =============================================================================
# Covers: the happy path (download, SHA256 verify, write with SPDX header),
# checksum mismatch (refuse to write, non-zero exit), missing manifest entry,
# and checksum-manifest fetch failure. No network: a fake "curl" binary is
# installed first on PATH and serves payloads from environment variables.
#
# The stub computes nothing; the suite builds a manifest whose SHA256 matches
# the served payload so verification passes on the happy path.

load 'libs/bats-support/load'
load 'libs/bats-assert/load'

SCRIPT="$BATS_TEST_DIRNAME/../sync_org_files.sh"

# Files the script syncs (must mirror the FILES array in sync_org_files.sh).
FILES="CODE_OF_CONDUCT.md SECURITY.md CONTRIBUTING.md SUPPORT.md GOVERNANCE.md CODEOWNERS FUNDING.yml LICENSE pull_request_template.md dependabot.yml"

setup() {
  TEST_TMPDIR="$(mktemp -d)"
  BIN="$TEST_TMPDIR/bin"
  WORKDIR="$TEST_TMPDIR/work"
  mkdir -p "$BIN" "$WORKDIR"
  export TEST_TMPDIR BIN
  export PATH="$BIN:/usr/local/bin:/bin:/usr/bin"

  PAYLOAD="HELLO PAYLOAD"
  SHA="$(printf '%s' "$PAYLOAD" | sha256sum | awk '{print $1}')"
  export PAYLOAD SHA
  export MANIFEST="$(_manifest "$SHA")"

  _write_curl_stub
  cd "$WORKDIR"
}

teardown() { rm -rf "$TEST_TMPDIR"; }

# _manifest <sha>  ->  "<sha>  <file>" lines for every synced file.
_manifest() {
  local sha="$1" f out=""
  for f in $FILES; do
    out+="$sha  $f"$'\n'
  done
  printf '%s' "$out"
}

# curl stub. Serves $MANIFEST for any checksums.txt URL and $PAYLOAD for
# everything else. FAIL_CHECKSUMS=1 makes the checksums fetch fail.
_write_curl_stub() {
  cat > "$BIN/curl" <<'STUB'
#!/usr/bin/env bash
outfile=""; url=""; prev=""
for a in "$@"; do
  [ "$prev" = "-o" ] && outfile="$a"
  case "$a" in https://*) url="$a" ;; esac
  prev="$a"
done
case "$url" in
  */checksums.txt)
    if [ "${FAIL_CHECKSUMS:-0}" = "1" ]; then exit 1; fi
    printf '%s' "$MANIFEST" > "$outfile" ;;
  *)
    printf '%s' "$PAYLOAD" > "$outfile" ;;
esac
exit 0
STUB
  chmod +x "$BIN/curl"
}

@test "happy path: verifies and writes every file with the SPDX header" {
  run bash "$SCRIPT"
  assert_success
  assert_output --partial "All files synced"
  assert [ -f "$WORKDIR/CODE_OF_CONDUCT.md" ]
  # REUSE-IgnoreStart -- the literal tag below is test data, not this file's license
  run grep -q "SPDX-License-Identifier: MIT" "$WORKDIR/CODE_OF_CONDUCT.md"
  # REUSE-IgnoreEnd
  assert_success
  run grep -q "HELLO PAYLOAD" "$WORKDIR/CODE_OF_CONDUCT.md"
  assert_success
}

@test "checksum mismatch: refuses to write and exits non-zero" {
  local bad_sha="0000000000000000000000000000000000000000000000000000000000000000"
  MANIFEST="$(_manifest "$bad_sha")" run bash "$SCRIPT"
  assert_failure
  assert_output --partial "SHA256 mismatch"
  assert [ ! -f "$WORKDIR/CODE_OF_CONDUCT.md" ]
}

@test "missing manifest entry: aborts with a clear error" {
  MANIFEST="" run bash "$SCRIPT"
  assert_failure
  assert_output --partial "No checksum recorded"
}

@test "checksum-manifest fetch failure: aborts" {
  FAIL_CHECKSUMS=1 run bash "$SCRIPT"
  assert_failure
  assert_output --partial "Failed to fetch checksums.txt"
}
