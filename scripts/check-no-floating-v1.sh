#!/usr/bin/env bash
# check-no-floating-v1.sh: Fail if any staged file pins an org reusable
# workflow to a bare floating major tag (@v1, @v2, ...), or reintroduces
# followTag into a Renovate config. The org tag-protection ruleset makes
# every v* tag immutable, so a floating major tag cannot exist; a bare @vN
# reference silently freezes callers on stale workflow code. Pin a full
# 40-char SHA with a release-tag comment (@<sha> # vX.Y.Z) or an immutable
# point tag (@vX.Y.Z) instead.
# The path exclusions below apply to BOTH checks: tag-pin fixtures, vendored
# test libs, historical audit records, and the tests/*.bats suites all embed
# @v1 literals (or followTag keys) as intentional fixture data.
# Called by the no-floating-v1 pre-commit hook.
set -euo pipefail

# Bare @vN with no dot-digit continuation (allows @v1.1.0, blocks @v1, @v2,
# @v10). The grep below is case-insensitive because GitHub resolves the
# uses: owner/repo portion case-insensitively, so a lowercased org name
# still executes in Actions.
PATTERN='(ByronWilliamsCPA|williaby)/\.github/\.github/workflows/[^@[:space:]]+@v[0-9]+([^.0-9]|$)'

# Route the staged-file listing through a temp file: a process
# substitution's exit status is invisible to set -e, so
# `mapfile < <(git ...)` would convert any git failure (corrupt index,
# permission error) into "no staged files" and pass vacuously. A guard
# must fail closed.
staged_list=$(mktemp)
trap 'rm -f "${staged_list}"' EXIT
git diff --cached --diff-filter=d -z --name-only >"${staged_list}"
mapfile -d '' staged_files <"${staged_list}"

found=()
for file in "${staged_files[@]}"; do
  case "${file}" in
    tests/fixtures/*|tests/libs/*|docs/audits/*|tests/*.bats) continue ;;
  esac
  # grep exit 0 = match, 1 = clean, >= 2 = error. An unreadable or
  # vanished file must fail the hook, never silently pass it.
  status=0
  LC_ALL=C grep -Eiq -- "${PATTERN}" "${file}" || status=$?
  if [[ ${status} -eq 0 ]]; then
    found+=("${file}")
  elif [[ ${status} -ge 2 ]]; then
    echo "check-no-floating-v1: cannot read staged file: ${file}" >&2
    exit 1
  fi
  case "$(basename "${file}")" in
    renovate.json|renovate.json5|.renovaterc|.renovaterc.json|.renovaterc.json5)
      # Unquoted-key tolerant: JSON5 configs may write followTag: without
      # surrounding double quotes. Line-anchored so prose inside a rule
      # description (e.g. "No followTag: the org ruleset...") does not
      # trip the guard; a real key always starts its own line in
      # formatted config.
      status=0
      grep -Eq -- '^[[:space:]]*"?followTag"?[[:space:]]*:' "${file}" || status=$?
      if [[ ${status} -eq 0 ]]; then
        found+=("${file} (followTag)")
      elif [[ ${status} -ge 2 ]]; then
        echo "check-no-floating-v1: cannot read staged file: ${file}" >&2
        exit 1
      fi
      ;;
  esac
done

if [[ ${#found[@]} -gt 0 ]]; then
  echo "Floating major tag (@vN) or followTag referenced in the following files:"
  for f in "${found[@]}"; do
    echo "  ${f}"
  done
  echo "No floating major tag exists (org tag ruleset makes v* tags immutable)."
  echo "Pin org workflows to @<full-sha> # vX.Y.Z or an immutable @vX.Y.Z tag."
  exit 1
fi

exit 0
