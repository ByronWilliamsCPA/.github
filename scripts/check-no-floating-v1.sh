#!/usr/bin/env bash
# check-no-floating-v1.sh: Fail if any staged file pins an org reusable
# workflow to the retired floating v1 tag, or reintroduces followTag into
# renovate.json. The org tag-protection ruleset makes every v* tag immutable,
# so a floating major tag cannot exist; @v1 references silently freeze
# callers on stale workflow code. Pin a full 40-char SHA with a release-tag
# comment (@<sha> # vX.Y.Z) or an immutable point tag (@vX.Y.Z) instead.
# Called by the no-floating-v1 pre-commit hook.
set -euo pipefail

# @v1 not followed by a dot-digit continuation (allows @v1.1.0, blocks @v1)
PATTERN='(ByronWilliamsCPA|williaby)/\.github/\.github/workflows/[^@[:space:]]+@v1([^.0-9]|$)'

mapfile -d '' staged_files < <(git diff --cached --diff-filter=d -z --name-only)

found=()
for file in "${staged_files[@]}"; do
  # Intentional tag-pin fixtures, vendored test libs, and historical audit
  # records are allowed to keep @v1 references.
  case "${file}" in
    tests/fixtures/*|tests/libs/*|docs/audits/*) continue ;;
  esac
  if LC_ALL=C grep -Eql "${PATTERN}" "${file}" 2>/dev/null; then
    found+=("${file}")
  fi
  if [[ "$(basename "${file}")" == "renovate.json" ]] \
    && grep -ql '"followTag"' "${file}" 2>/dev/null; then
    found+=("${file} (followTag)")
  fi
done

if [[ ${#found[@]} -gt 0 ]]; then
  echo "Retired floating v1 tag referenced in the following files:"
  for f in "${found[@]}"; do
    echo "  ${f}"
  done
  echo "No floating major tag exists (org tag ruleset makes v* tags immutable)."
  echo "Pin org workflows to @<full-sha> # vX.Y.Z or an immutable @vX.Y.Z tag."
  exit 1
fi

exit 0
