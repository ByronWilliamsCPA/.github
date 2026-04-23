#!/usr/bin/env bash
# =============================================================================
# GitHub Actions Pin Updater
# =============================================================================
# Scans workflow files for pinned GitHub Actions and checks for updates within
# the same major version. Fetches the latest commit SHA for each action's
# current major version tag via the GitHub API.
#
# Dry-run by default: shows proposed changes without modifying files.
# After manual review, re-run with --apply to write changes.
#
# Usage:
#   ./scripts/update-pinned-actions.sh
#   ./scripts/update-pinned-actions.sh --apply
#   ./scripts/update-pinned-actions.sh --workflows-dir .github/workflows
#
# Options:
#   --apply            Write changes to workflow files (default: dry-run)
#   --workflows-dir    Override workflow directory (default: .github/workflows)
#   -h, --help         Show this help
#
# Requirements:
#   - gh CLI installed and authenticated (gh auth login)
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WORKFLOWS_DIR="$REPO_ROOT/.github/workflows"
APPLY=false

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

usage() {
    local exit_code="${1:-0}"
    sed -n '/^# Usage:/,/^# Requirements:/p' "$0" | sed 's/^# //' | sed 's/^#//'
    exit "$exit_code"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --apply)           APPLY=true; shift ;;
        --workflows-dir)
            if [[ $# -lt 2 || -z "${2:-}" ]]; then
                echo -e "${RED}ERROR: --workflows-dir requires a directory path${NC}"
                usage 1
            fi
            WORKFLOWS_DIR="$2"
            shift 2
            ;;
        -h|--help)         usage 0 ;;
        *) echo -e "${RED}Unknown option: $1${NC}"; usage 1 ;;
    esac
done

# ---------------------------------------------------------------------------
# Prerequisites
# ---------------------------------------------------------------------------
if ! command -v gh &>/dev/null; then
    echo -e "${RED}ERROR: gh CLI not found. Install from https://cli.github.com${NC}"
    exit 1
fi

if ! gh auth status &>/dev/null 2>&1; then
    echo -e "${RED}ERROR: gh CLI not authenticated. Run: gh auth login${NC}"
    exit 1
fi

if [[ ! -d "$WORKFLOWS_DIR" ]]; then
    echo -e "${RED}ERROR: Workflows directory not found: $WORKFLOWS_DIR${NC}"
    exit 1
fi

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
echo -e "${BLUE}╔══════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║      GitHub Actions Pin Updater              ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo "  Mode : $([ "$APPLY" = true ] && echo -e "${YELLOW}APPLY: files will be modified${NC}" || echo -e "${CYAN}DRY RUN: no files will be changed${NC}")"
echo "  Dir  : $WORKFLOWS_DIR"
echo ""

# ---------------------------------------------------------------------------
# Resolve a tag to its commit SHA (handles annotated + lightweight tags)
# ---------------------------------------------------------------------------
resolve_tag_sha() {
    local repo="$1"
    local tag="$2"

    local obj_type obj_sha
    obj_type=$(gh api "repos/$repo/git/refs/tags/$tag" --jq '.object.type' 2>/dev/null) || { echo ""; return; }
    obj_sha=$(gh api "repos/$repo/git/refs/tags/$tag" --jq '.object.sha' 2>/dev/null) || { echo ""; return; }

    if [[ "$obj_type" == "tag" ]]; then
        # Annotated tag: resolve tag object to its target commit SHA
        obj_sha=$(gh api "repos/$repo/git/tags/$obj_sha" --jq '.object.sha' 2>/dev/null) || { echo ""; return; }
    fi

    echo "$obj_sha"
}

# ---------------------------------------------------------------------------
# Extract unique pinned action references from all workflow files
# Pattern: uses: owner/repo[/subpath]@<40-char-sha>  # vX.Y.Z
# ---------------------------------------------------------------------------
UNIQUE_ACTIONS_FILE=$(mktemp)
CHANGE_LOG=$(mktemp)
trap 'rm -f "$UNIQUE_ACTIONS_FILE" "$CHANGE_LOG"' EXIT

grep -rh "uses:" "$WORKFLOWS_DIR"/ \
    | grep -oE '[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+(/[a-zA-Z0-9_./-]*)?@[a-f0-9]{40}[[:space:]]+#[[:space:]]+v[0-9]+(\.[0-9.]+)*' \
    | sort -u \
    > "$UNIQUE_ACTIONS_FILE" || true

TOTAL=$(wc -l < "$UNIQUE_ACTIONS_FILE" | tr -d ' ')
echo "Found $TOTAL unique pinned action references"
echo ""
printf "%-55s %-10s   %s\n" "Action" "Current" "Latest"
printf '%0.s─' {1..80}; echo ""

UP_TO_DATE=0
UPDATES=0
SKIPPED=0

while IFS= read -r entry; do
    [[ -z "$entry" ]] && continue

    # Parse fields from the entry string
    full_action="${entry%%@*}"
    current_sha=$(echo "$entry" | grep -oE '[a-f0-9]{40}' | head -1)
    current_version=$(echo "$entry" | grep -oE 'v[0-9]+(\.[0-9]+)*$')

    # Derive the repo (first two path segments, strip any sub-action path)
    repo=$(echo "$full_action" | awk -F/ '{print $1"/"$2}')

    # Major version prefix for filtering releases (e.g. "v4" from "v4.2.2")
    major=$(echo "$current_version" | grep -oE '^v[0-9]+')

    # Find the latest release tag within the same major version
    latest_version=$(
        gh release list --repo "$repo" --limit 50 --json tagName \
            --jq "[.[] | select(.tagName | test(\"^${major}[.]\")) | .tagName] | sort_by(split(\".\") | map(ltrimstr(\"v\") | tonumber? // 0)) | reverse | first // empty" \
            2>/dev/null || true
    )

    # Some repos tag without a patch component (e.g. v2 only); fall back gracefully
    if [[ -z "$latest_version" ]]; then
        latest_version=$(
            gh release list --repo "$repo" --limit 50 --json tagName \
                --jq "[.[] | select(.tagName == \"${major}\")] | first | .tagName // empty" \
                2>/dev/null || true
        )
    fi

    if [[ -z "$latest_version" ]]; then
        printf "%-55s %-10s   %b\n" "$full_action" "$current_version" "${YELLOW}SKIP: no releases found${NC}"
        ((SKIPPED++)) || true
        continue
    fi

    # Resolve the latest version tag to its commit SHA
    new_sha=$(resolve_tag_sha "$repo" "$latest_version")

    if [[ -z "$new_sha" ]]; then
        printf "%-55s %-10s   %b\n" "$full_action" "$current_version" "${YELLOW}SKIP: could not resolve SHA${NC}"
        ((SKIPPED++)) || true
        continue
    fi

    if [[ "$current_sha" == "$new_sha" && "$current_version" == "$latest_version" ]]; then
        printf "%-55s %-10s   %b\n" "$full_action" "$current_version" "${GREEN}up to date${NC}"
        ((UP_TO_DATE++)) || true
    else
        printf "%-55s %-10s → %b\n" "$full_action" "$current_version" "${YELLOW}${latest_version}  (${new_sha:0:12}...)${NC}"
        printf '%s|%s|%s|%s|%s\n' \
            "$full_action" "$current_sha" "$current_version" "$new_sha" "$latest_version" \
            >> "$CHANGE_LOG"
        ((UPDATES++)) || true
    fi

done < "$UNIQUE_ACTIONS_FILE"

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
printf '%0.s─' {1..80}; echo ""
echo ""
echo -e "  ${GREEN}Up to date : $UP_TO_DATE${NC}"
echo -e "  ${YELLOW}Updates    : $UPDATES${NC}"
[[ $SKIPPED -gt 0 ]] && echo -e "  ${YELLOW}Skipped    : $SKIPPED (check manually)${NC}"
echo ""

if [[ $UPDATES -eq 0 ]]; then
    echo -e "${GREEN}All pinned actions are up to date.${NC}"
    exit 0
fi

# ---------------------------------------------------------------------------
# Detailed change summary (always shown, regardless of --apply)
# ---------------------------------------------------------------------------
echo -e "${BLUE}Proposed changes:${NC}"
echo ""
while IFS='|' read -r full_action current_sha current_version new_sha latest_version; do
    echo -e "  ${CYAN}$full_action${NC}"
    echo    "    - $current_version  @$current_sha"
    echo    "    + $latest_version  @$new_sha"
    echo ""
done < "$CHANGE_LOG"

# ---------------------------------------------------------------------------
# Dry-run exit
# ---------------------------------------------------------------------------
if [[ "$APPLY" = false ]]; then
    echo -e "${CYAN}DRY RUN complete: no files were changed.${NC}"
    echo ""
    echo "Review the changes above, then run with --apply to update workflow files:"
    echo "  ./scripts/update-pinned-actions.sh --apply"
    exit 0
fi

# ---------------------------------------------------------------------------
# Apply changes
# ---------------------------------------------------------------------------
echo -e "${YELLOW}Applying changes...${NC}"
echo ""

declare -A FILES_CHANGED

while IFS='|' read -r full_action current_sha current_version new_sha latest_version; do
    # Find every workflow file containing this action+sha and update it
    while IFS= read -r wf_file; do
        tmp_wf=$(mktemp)
        sed \
            "s|${full_action}@${current_sha}[[:space:]]*#[[:space:]]*${current_version}|${full_action}@${new_sha}  # ${latest_version}|g" \
            "$wf_file" > "$tmp_wf"
        mv "$tmp_wf" "$wf_file"
        FILES_CHANGED["$wf_file"]=1
    done < <(grep -rl "${full_action}@${current_sha}" "$WORKFLOWS_DIR"/ 2>/dev/null)

done < "$CHANGE_LOG"

echo "Files updated:"
for f in "${!FILES_CHANGED[@]}"; do
    echo "  $(basename "$f")"
done | sort

echo ""
echo -e "${GREEN}Done.${NC}"
echo ""
echo "Next steps:"
echo "  1. git diff .github/workflows/   # review all changes"
echo "  2. Trigger a workflow run to validate nothing broke"
echo "  3. git add .github/workflows/ && git commit -m 'chore(ci): bump pinned action SHAs to latest'"
