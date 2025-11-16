#!/usr/bin/env bash
set -euo pipefail

# SPDX header + compliance note
HEADER='<!-- SPDX-FileCopyrightText: © 2019–2025 Byron Williams -->
<!-- SPDX-License-Identifier: MIT -->

> **NOTE:** This file is maintained centrally in the organization’s `.github` repository.
> For the latest version, see:
> https://github.com/williaby/.github/blob/main/{{FILE_PATH}}'

# Files to sync
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
  ".github/ISSUE_TEMPLATE/bug.yml"
  ".github/ISSUE_TEMPLATE/feature.yml"
  ".github/ISSUE_TEMPLATE/config.yml"
)

for f in "${FILES[@]}"; do
  org_url="https://raw.githubusercontent.com/williaby/.github/main/$f"
  echo ">>> Syncing $f from $org_url"
  mkdir -p "$(dirname "$f")"
  {
    # 1) SPDX header + replace placeholder
    printf "%s\n\n" "$HEADER" | sed "s|{{FILE_PATH}}|$f|g"
    # 2) Org-level content
    curl --fail -s "$org_url"
  } > "$f"
done

echo "✓ All files synced."
