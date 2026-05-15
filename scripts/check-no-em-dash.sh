#!/usr/bin/env bash
# check-no-em-dash.sh: Fail if any staged file contains an em-dash (U+2014).
# Called by the no-em-dash pre-commit hook (PC-011).
set -euo pipefail

EM_DASH=$'\xe2\x80\x94'

mapfile -d '' staged_files < <(git diff --cached --diff-filter=d -z --name-only)

found=()
for file in "${staged_files[@]}"; do
  if LC_ALL=C grep -ql "${EM_DASH}" "${file}" 2>/dev/null; then
    found+=("${file}")
  fi
done

if [[ ${#found[@]} -gt 0 ]]; then
  echo "Em-dash (U+2014) found in the following files:"
  for f in "${found[@]}"; do
    echo "  ${f}"
  done
  echo "Replace em-dashes with a comma, semicolon, or colon."
  exit 1
fi

exit 0
