#!/usr/bin/env bash
# =============================================================================
# Fleet-wide SHA-pin audit
# =============================================================================
# For every repo in the specified org(s), reads each .github/workflows/*.yml
# via the GitHub API and counts references whose owner is NOT in the
# --skip-owners list (default: ByronWilliamsCPA,williaby) and whose ref is a
# tag (@v...) or branch (@main/@master/@HEAD/@develop).
#
# Output: CSV with one row per repo: repo,violations
# Exit code: 0 even when violations exist (this is a report, not a gate).
#
# Usage:
#   ./scripts/fleet-audit-sha-pins.sh --org ByronWilliamsCPA [--org williaby] \
#     [--skip-owners ByronWilliamsCPA,williaby] [--output audit.csv]
# =============================================================================

set -euo pipefail

ORGS=()
SKIP_OWNERS="ByronWilliamsCPA,williaby"
OUTPUT="-"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --org)          ORGS+=("$2"); shift 2 ;;
        --skip-owners)  SKIP_OWNERS="$2"; shift 2 ;;
        --output)       OUTPUT="$2"; shift 2 ;;
        -h|--help)      sed -n '/^# Usage:/,/^# ===/p' "$0" | sed 's/^# //'; exit 0 ;;
        *) echo "Unknown: $1" >&2; exit 1 ;;
    esac
done

[[ ${#ORGS[@]} -eq 0 ]] && { echo "ERROR: --org required (repeatable)" >&2; exit 1; }
command -v gh >/dev/null || { echo "ERROR: gh CLI not found" >&2; exit 1; }
gh auth status >/dev/null 2>&1 || { echo "ERROR: gh not authenticated" >&2; exit 1; }

# Matches uses: OWNER/REPO@REF where REF is a tag (v1.2.3) or branch name.
# Handles both top-level "uses:" and YAML step "- uses:" forms.
# A 40-character hex string (SHA) does NOT match this pattern.
# The pattern excludes refs that are exactly 40 hex chars (full SHA pins).
TAG_OR_BRANCH_RE='^[[:space:]]*(- )?uses:[[:space:]]+([a-zA-Z0-9_.-]+)/[a-zA-Z0-9_.-]+(/[a-zA-Z0-9_./-]*)?@([^[:space:]#]+)'

emit() {
    if [[ "$OUTPUT" == "-" ]]; then
        printf '%s\n' "$1"
    else
        printf '%s\n' "$1" >> "$OUTPUT"
    fi
}

[[ "$OUTPUT" != "-" ]] && : > "$OUTPUT"
emit "repo,violations"

for org in "${ORGS[@]}"; do
    mapfile -t repos < <(gh repo list "$org" --limit 200 --json name --jq '.[].name')
    for repo in "${repos[@]}"; do
        full="$org/$repo"
        # Skip infrastructure meta-repos
        case "$full" in
            ByronWilliamsCPA/.github|ByronWilliamsCPA/.claude|williaby/.github|williaby/.claude) continue ;;
        esac

        files=$(gh api "repos/$full/contents/.github/workflows" --jq '.[].path' 2>/dev/null || true)
        [[ -z "$files" ]] && { emit "$full,0"; continue; }

        violations=0
        while IFS= read -r path; do
            [[ -z "$path" ]] && continue
            [[ "$path" != *.yml && "$path" != *.yaml ]] && continue
            content=$(gh api "repos/$full/contents/$path" --jq '.content' 2>/dev/null | base64 -d 2>/dev/null || true)
            [[ -z "$content" ]] && continue
            while IFS= read -r line; do
                # Skip comment lines
                [[ "$line" =~ ^[[:space:]]*# ]] && continue
                if [[ "$line" =~ $TAG_OR_BRANCH_RE ]]; then
                    owner="${BASH_REMATCH[2]}"
                    ref="${BASH_REMATCH[4]}"
                    # Skip if owner is in the skip list
                    if [[ "$owner" =~ ^(${SKIP_OWNERS//,/|})$ ]]; then
                        continue
                    fi
                    # Skip if ref is a full 40-character SHA (already pinned)
                    if [[ "$ref" =~ ^[0-9a-f]{40}$ ]]; then
                        continue
                    fi
                    violations=$((violations + 1))
                fi
            done <<< "$content"
        done <<< "$files"

        emit "$full,$violations"
    done
done
