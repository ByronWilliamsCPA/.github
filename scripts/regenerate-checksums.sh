#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# Regenerate checksums.txt for files synced by sync_org_files.sh.
#
# Run this whenever any file in the sync list changes. The output is written
# to checksums.txt at the repo root and must be committed alongside the file
# change in the same commit. Out-of-sync checksums.txt fails downstream sync
# operations.
#
# The file list MUST stay in sync with FILES in sync_org_files.sh.
# ============================================================================

cd "$(dirname "$0")/.."

FILES=(
  "CODE_OF_CONDUCT.md"
  "SECURITY.md"
  "CONTRIBUTING.md"
  "SUPPORT.md"
  "GOVERNANCE.md"
  "CODEOWNERS"
  "FUNDING.yml"
  "LICENSE"
  "pull_request_template.md"
  "dependabot.yml"
)

# Verify every file in the list exists before writing the manifest.
missing=()
for f in "${FILES[@]}"; do
  if [[ ! -f "$f" ]]; then
    missing+=("$f")
  fi
done
if [[ "${#missing[@]}" -gt 0 ]]; then
  echo "ERROR: The following files are listed but missing from the working tree:" >&2
  printf '  %s\n' "${missing[@]}" >&2
  exit 1
fi

# Write manifest. Trailing newline preserved.
tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
for f in "${FILES[@]}"; do
  sha256sum "$f"
done > "$tmp"
mv "$tmp" checksums.txt
trap - EXIT

echo "✓ checksums.txt regenerated with ${#FILES[@]} entries."
