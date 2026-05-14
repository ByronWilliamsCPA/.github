#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# Sync org-level files from ByronWilliamsCPA/.github main branch with SHA256
# integrity verification.
#
# Each file listed in FILES is downloaded from raw.githubusercontent.com and
# verified against an authoritative checksums.txt manifest fetched from the
# same source. Files that fail verification are NOT written; the script aborts
# with a non-zero exit code so the calling repo can detect the failure.
#
# Updating tracked files requires a coordinated change: edit the file in this
# repo's main branch AND regenerate checksums.txt in the same commit (see
# scripts/regenerate-checksums.sh). The pre-commit checksum hook in
# .pre-commit-config.yaml enforces this locally.
# ============================================================================

ORG_REPO="ByronWilliamsCPA/.github"
ORG_BRANCH="main"
RAW_BASE="https://raw.githubusercontent.com/${ORG_REPO}/${ORG_BRANCH}"

# SPDX header + compliance note, prepended to each synced file
HEADER="<!-- SPDX-FileCopyrightText: © 2019–2025 Byron Williams -->
<!-- SPDX-License-Identifier: MIT -->

> **NOTE:** This file is maintained centrally in the organization's \`.github\` repository.
> For the latest version, see:
> https://github.com/${ORG_REPO}/blob/${ORG_BRANCH}/{{FILE_PATH}}"

# Files to sync. Must match entries in checksums.txt at the org repo root.
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

# Step 1: Stage workspace
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

# Step 2: Fetch authoritative checksum manifest
CHECKSUMS_FILE="${TMPDIR}/checksums.txt"
echo ">>> Fetching ${RAW_BASE}/checksums.txt"
if ! curl --fail --proto '=https' --tlsv1.2 -sL "${RAW_BASE}/checksums.txt" -o "${CHECKSUMS_FILE}"; then
  echo "ERROR: Failed to fetch checksums.txt from ${RAW_BASE}" >&2
  echo "       The org repo must publish a checksums.txt manifest at its root" >&2
  echo "       before downstream repos can sync files. See sync_org_files.sh" >&2
  echo "       documentation for details." >&2
  exit 1
fi

# Step 3: Sync and verify each file
for f in "${FILES[@]}"; do
  org_url="${RAW_BASE}/${f}"
  echo ">>> Syncing $f"

  # Download to temp file
  tmp_payload="${TMPDIR}/payload"
  if ! curl --fail -s "$org_url" -o "$tmp_payload"; then
    echo "ERROR: Failed to download $f from $org_url" >&2
    exit 1
  fi

  # Look up expected SHA256 in the manifest. Manifest format is:
  # <sha256>  <relative_path>
  # Use word-boundary anchored grep against the path to avoid prefix matches.
  expected="$(awk -v path="$f" '$2 == path {print $1}' "${CHECKSUMS_FILE}")"
  if [ -z "$expected" ]; then
    echo "ERROR: No checksum recorded for $f in ${RAW_BASE}/checksums.txt" >&2
    echo "       The file is in the sync list but missing from the manifest." >&2
    echo "       This is a publishing-side bug in the org repo; abort." >&2
    exit 1
  fi

  actual="$(sha256sum "$tmp_payload" | awk '{print $1}')"
  if [ "$expected" != "$actual" ]; then
    echo "ERROR: SHA256 mismatch for $f" >&2
    echo "       expected: $expected" >&2
    echo "       actual:   $actual" >&2
    echo "       Refusing to write the file. The org repo's checksums.txt may" >&2
    echo "       be stale, or the file was modified out of band." >&2
    exit 1
  fi

  # Step 4: Verification passed — write final file with SPDX header
  mkdir -p "$(dirname "$f")"
  {
    printf "%s\n\n" "$HEADER" | sed "s|{{FILE_PATH}}|$f|g"
    cat "$tmp_payload"
  } > "$f"
done

echo "✓ All files synced and SHA256-verified."
