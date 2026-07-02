#!/usr/bin/env bats
# =============================================================================
# Tests for scripts/check-no-floating-v1.sh
# =============================================================================
# Covers: the bare @vN org-workflow guard (retired @v1, future bare majors,
# case-insensitive org match), the allowed pin forms (@vX.Y.Z point tags,
# 40-char SHA pins, third-party @v1 actions), the path exclusions
# (tests/fixtures/*, tests/libs/*, docs/audits/*, tests/*.bats), the
# followTag guard across Renovate config basenames (quoted and unquoted
# keys), and the fail-closed behavior when git itself fails. Each test runs
# the script against a throwaway git repo with files staged via git add; the
# script reads `git diff --cached`, so staging is the fixture mechanism. No
# network access required.

load 'libs/bats-support/load'
load 'libs/bats-assert/load'

SCRIPT="$BATS_TEST_DIRNAME/../scripts/check-no-floating-v1.sh"

setup() {
  TEST_TMPDIR="$(mktemp -d)"
  REPO_DIR="$TEST_TMPDIR/repo"
  mkdir -p "$REPO_DIR"
  git -C "$REPO_DIR" init --quiet
  export TEST_TMPDIR REPO_DIR
}

teardown() { rm -rf "$TEST_TMPDIR"; }

# Stage a file with the given repo-relative path and content, creating
# parent directories as needed.
_stage() {
  local path="$1" content="$2"
  mkdir -p "$REPO_DIR/$(dirname "$path")"
  printf '%s\n' "$content" > "$REPO_DIR/$path"
  git -C "$REPO_DIR" add "$path"
}

_run_hook() { (cd "$REPO_DIR" && "$SCRIPT"); }

@test "blocks bare @v1 on an org workflow uses: line" {
  _stage "caller.yml" "    uses: ByronWilliamsCPA/.github/.github/workflows/python-ci.yml@v1"
  run _run_hook
  assert_failure
  assert_output --partial "caller.yml"
}

@test "blocks bare @v1 inside a comment line" {
  _stage "doc.md" "#   uses: ByronWilliamsCPA/.github/.github/workflows/python-ci.yml@v1"
  run _run_hook
  assert_failure
}

@test "blocks bare @v1 for the williaby org" {
  _stage "caller.yml" "    uses: williaby/.github/.github/workflows/release-tag.yml@v1"
  run _run_hook
  assert_failure
}

@test "blocks a lowercased org name (GitHub resolves uses: case-insensitively)" {
  _stage "caller.yml" "    uses: byronwilliamscpa/.github/.github/workflows/python-ci.yml@v1"
  run _run_hook
  assert_failure
}

@test "blocks future bare majors like @v2 and @v10" {
  _stage "caller.yml" "    uses: ByronWilliamsCPA/.github/.github/workflows/python-ci.yml@v2"
  run _run_hook
  assert_failure
  git -C "$REPO_DIR" reset --quiet
  _stage "caller2.yml" "    uses: ByronWilliamsCPA/.github/.github/workflows/python-ci.yml@v10"
  run _run_hook
  assert_failure
}

@test "allows immutable point tags like @v1.1.0" {
  _stage "caller.yml" "    uses: ByronWilliamsCPA/.github/.github/workflows/python-ci.yml@v1.1.0"
  run _run_hook
  assert_success
}

@test "allows full-SHA pins with a release-tag comment" {
  _stage "caller.yml" "    uses: ByronWilliamsCPA/.github/.github/workflows/python-ci.yml@d5cf99101d4150ae5832d154cb42993705a09e31 # v7.0.1"
  run _run_hook
  assert_success
}

@test "allows third-party actions at @v1 (guard is org-workflow scoped)" {
  _stage "caller.yml" "    uses: codelytv/pr-size-labeler@v1"
  run _run_hook
  assert_success
}

@test "excludes tests/fixtures/, tests/libs/, docs/audits/, and tests/*.bats" {
  _stage "tests/fixtures/workflows/tag-pinned.yml" "  uses: ByronWilliamsCPA/.github/.github/workflows/python-ci.yml@v1"
  _stage "tests/libs/vendored.sh" "uses: ByronWilliamsCPA/.github/.github/workflows/python-ci.yml@v1"
  _stage "docs/audits/2026-01-01/report.md" "uses: williaby/.github/.github/workflows/release-tag.yml@v1"
  _stage "tests/some-suite.bats" 'run grep -F "ByronWilliamsCPA/.github/.github/workflows/python-ci.yml@v1"'
  run _run_hook
  assert_success
}

@test "blocks quoted followTag in renovate.json" {
  _stage "renovate.json" '{"packageRules": [{"followTag": "v1"}]}'
  run _run_hook
  assert_failure
  assert_output --partial "followTag"
}

@test "blocks unquoted followTag in renovate.json5" {
  _stage "renovate.json5" '{ packageRules: [{ followTag: "v1" }] }'
  run _run_hook
  assert_failure
  assert_output --partial "followTag"
}

@test "allows renovate.json without followTag" {
  _stage "renovate.json" '{"packageRules": [{"versioning": "semver"}]}'
  run _run_hook
  assert_success
}

@test "allows followTag mentioned in a renovate.json description string" {
  # A rule description may explain WHY followTag is absent; only a real
  # key (line-anchored) may trip the guard.
  _stage "renovate.json" '{
  "packageRules": [
    {
      "description": "No followTag: the org ruleset makes v* tags immutable.",
      "versioning": "semver"
    }
  ]
}'
  run _run_hook
  assert_success
}

@test "passes with nothing staged" {
  run _run_hook
  assert_success
}

@test "prose mentions of followTag outside Renovate configs pass" {
  _stage "CHANGELOG.md" 'Removed followTag: "v1" from renovate.json so pins advance.'
  run _run_hook
  assert_success
}

@test "fails closed when git itself fails (not a repository)" {
  NOT_A_REPO="$TEST_TMPDIR/plain"
  mkdir -p "$NOT_A_REPO"
  run bash -c "cd '$NOT_A_REPO' && GIT_CEILING_DIRECTORIES='$TEST_TMPDIR' '$SCRIPT'"
  assert_failure
}
