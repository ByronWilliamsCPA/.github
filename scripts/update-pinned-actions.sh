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
PIN_TAGS=false
OWNER_ALLOWLIST="ByronWilliamsCPA,williaby"

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
        --pin-tags)        PIN_TAGS=true; shift ;;
        --owner-allowlist)
            if [[ $# -lt 2 || -z "${2:-}" ]]; then
                echo -e "${RED}ERROR: --owner-allowlist requires a comma-separated list${NC}"
                usage 1
            fi
            OWNER_ALLOWLIST="$2"
            shift 2
            ;;
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
# Escape ERE metacharacters and the sed delimiter (|) in a string so it
# can be used as a literal sed pattern under `sed -E`. Implemented via
# sed rather than ${var//pat/rep} because the parameter-expansion form
# has a parser gotcha when the replacement contains `{` or `}`: the
# expansion's closing `}` consumes the wrong brace and the outer `}`
# leaks into the result.
# Bracket expression rules: `]` is first so it is literal; `\` must be
# escaped (sed sees `\\` as literal `\`).
# ---------------------------------------------------------------------------
escape_sed_pat() {
    printf '%s' "$1" | sed -e 's/[][\\.^$*+?(){}|]/\\&/g'
}

# ---------------------------------------------------------------------------
# Resolve a tag to its commit SHA (handles annotated + lightweight tags)
# ---------------------------------------------------------------------------
resolve_tag_sha() {
    local repo="$1"
    local tag="$2"

    # Fetch type and sha in a single API call so a force-push or rate-limit
    # hit between two separate fetches of the same ref cannot return
    # disagreeing values. The composite jq expression separates the two
    # fields with a `|`; tag types and SHAs never contain that character.
    local pair obj_type obj_sha
    pair=$(gh api "repos/$repo/git/refs/tags/$tag" \
        --jq '"\(.object.type)|\(.object.sha)"' 2>/dev/null) || { echo ""; return; }
    obj_type="${pair%%|*}"
    obj_sha="${pair#*|}"

    if [[ "$obj_type" == "tag" ]]; then
        # Annotated tag: resolve tag object to its target commit SHA
        obj_sha=$(gh api "repos/$repo/git/tags/$obj_sha" --jq '.object.sha' 2>/dev/null) || { echo ""; return; }
    fi

    echo "$obj_sha"
}

# ---------------------------------------------------------------------------
# Extract tag-pinned third-party action references
# Emits one record per line: "owner/repo[/sub]|tag"
# Skips owners in $OWNER_ALLOWLIST and branch refs (handled separately).
# Accepts trailing whitespace and optional "# comment" so refs annotated
# with an inline comment are not silently bypassed by the converter.
# ---------------------------------------------------------------------------
extract_tag_pins() {
    local raw grep_rc
    # Capture grep separately so we can distinguish "no matches" (rc=1, OK)
    # from real failures (rc>=2: unreadable dir, permission denied, regex
    # error). The previous `{ ...; } || true` form conflated both into
    # silent success, which contradicts the script's audit-honesty goal.
    raw=$(grep -rhE '^[[:space:]]*[#-]?[[:space:]]*uses:[[:space:]]+[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+(/[a-zA-Z0-9_./-]*)?@v[0-9]+(\.[0-9]+)*([[:space:]]+#.*)?[[:space:]]*$' \
        "$WORKFLOWS_DIR"/ 2>/dev/null) && grep_rc=0 || grep_rc=$?
    if [[ $grep_rc -ge 2 ]]; then
        echo "WARN: extract_tag_pins: grep failed rc=$grep_rc on $WORKFLOWS_DIR" >&2
        return 1
    fi
    [[ -z "$raw" ]] && return 0

    # Pass OWNER_ALLOWLIST verbatim to awk and do literal-string lookup
    # against the owner segment. Operator-supplied regex metacharacters
    # (`.`, `*`, `|`, etc.) are not interpreted: a value like `.*` is a
    # literal hash key and only matches an owner literally named `.*`.
    printf '%s\n' "$raw" \
        | grep -vE '^\s*#' \
        | sed -E 's/^[[:space:]]*-?[[:space:]]*uses:[[:space:]]+//; s/[[:space:]]+#.*$//; s/[[:space:]]*$//' \
        | awk -F'@' -v allowlist="$OWNER_ALLOWLIST" '
            BEGIN {
                n = split(allowlist, parts, ",")
                for (i = 1; i <= n; i++) {
                    if (parts[i] != "") skip[parts[i]] = 1
                }
            }
            {
                slash = index($1, "/")
                owner = (slash > 0) ? substr($1, 1, slash - 1) : $1
                if (!(owner in skip)) print $1 "|" $2
            }
          ' \
        | sort -u
}

# ---------------------------------------------------------------------------
# Extract branch-pinned third-party action references (reported, not converted)
# Accepts trailing whitespace and optional "# comment".
# ---------------------------------------------------------------------------
extract_branch_pins() {
    local raw grep_rc
    raw=$(grep -rhE '^[[:space:]]*-?[[:space:]]*uses:[[:space:]]+[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+(/[a-zA-Z0-9_./-]*)?@(main|master|HEAD|develop)([[:space:]]+#.*)?[[:space:]]*$' \
        "$WORKFLOWS_DIR"/ 2>/dev/null) && grep_rc=0 || grep_rc=$?
    if [[ $grep_rc -ge 2 ]]; then
        echo "WARN: extract_branch_pins: grep failed rc=$grep_rc on $WORKFLOWS_DIR" >&2
        return 1
    fi
    [[ -z "$raw" ]] && return 0

    printf '%s\n' "$raw" \
        | grep -vE '^\s*#' \
        | sed -E 's/^[[:space:]]*-?[[:space:]]*uses:[[:space:]]+//; s/[[:space:]]+#.*$//; s/[[:space:]]*$//' \
        | awk -F'@' -v allowlist="$OWNER_ALLOWLIST" '
            BEGIN {
                n = split(allowlist, parts, ",")
                for (i = 1; i <= n; i++) {
                    if (parts[i] != "") skip[parts[i]] = 1
                }
            }
            {
                slash = index($1, "/")
                owner = (slash > 0) ? substr($1, 1, slash - 1) : $1
                if (!(owner in skip)) print $0
            }
          ' \
        | sort -u
}

# ---------------------------------------------------------------------------
# --pin-tags mode entry point
# ---------------------------------------------------------------------------
pin_tags_main() {
    echo -e "${BLUE}Mode: PIN-TAGS (convert @vN refs to @<sha>)${NC}"
    echo "  Allowlist (skipped): $OWNER_ALLOWLIST"
    echo ""

    local pins
    pins=$(extract_tag_pins)
    if [[ -z "$pins" ]]; then
        echo -e "${GREEN}No third-party tag-pinned actions found. Repo is compliant with CI-060.${NC}"
    fi

    local branches
    branches=$(extract_branch_pins)
    if [[ -n "$branches" ]]; then
        echo -e "${YELLOW}WARN: branch ref detected (not auto-convertible, fix manually):${NC}"
        echo "$branches" | sed 's/^/  /'
        echo ""
    fi

    [[ -z "$pins" ]] && return 0

    # CHANGE_LOG is script-scope; the top-level EXIT trap handles cleanup.
    CHANGE_LOG=$(mktemp)

    printf "%-65s   %s\n" "Action@Tag" "Target SHA"
    printf '%0.s-' {1..90}; echo ""

    while IFS='|' read -r full_action current_tag; do
        [[ -z "$full_action" ]] && continue
        local ref repo major latest_tag new_sha
        ref="${full_action}@${current_tag}"
        repo=$(echo "$full_action" | awk -F/ '{print $1"/"$2}')
        major=$(echo "$current_tag" | grep -oE '^v[0-9]+')

        latest_tag=$(
            gh release list --repo "$repo" --limit 50 --json tagName \
              --jq "[.[] | select(.tagName | test(\"^${major}([.]|\$)\")) | .tagName] | sort_by(split(\".\") | map(ltrimstr(\"v\") | tonumber? // 0)) | reverse | first // empty" \
              2>/dev/null || true
        )
        if [[ -z "$latest_tag" ]]; then
            printf "%-65s   %b\n" "$ref" "${YELLOW}SKIP: no release found${NC}"
            continue
        fi

        new_sha=$(resolve_tag_sha "$repo" "$latest_tag")
        if [[ -z "$new_sha" ]]; then
            printf "%-65s   %b\n" "$ref" "${YELLOW}SKIP: cannot resolve SHA${NC}"
            continue
        fi

        printf "%-65s -> %b\n" "$ref" "${YELLOW}${latest_tag}  (${new_sha:0:12}...)${NC}"
        printf '%s|%s|%s|%s\n' "$full_action" "$current_tag" "$new_sha" "$latest_tag" >> "$CHANGE_LOG"
    done <<< "$pins"

    if [[ "$APPLY" = false ]]; then
        echo ""
        echo -e "${CYAN}DRY RUN complete: no files were changed.${NC}"
        return 0
    fi

    # Apply
    while IFS='|' read -r full_action current_tag new_sha latest_tag; do
        local _pat _rep safe_tag safe_action safe_current_tag
        # Escape sed-replacement metacharacters in latest_tag (the replacement
        # side). Order matters: backslash first.
        safe_tag="${latest_tag//\\/\\\\}"
        safe_tag="${safe_tag//&/\\&}"
        safe_tag="${safe_tag//|/\\|}"
        # Escape sed pattern metacharacters in BOTH the action ref and the
        # current tag before building _pat. A semver tag like "v4.2.1"
        # contains literal dots that would otherwise match any character;
        # a tag containing | (the sed delimiter) would terminate the pattern
        # field and append unintended sed commands.
        safe_action=$(escape_sed_pat "$full_action")
        safe_current_tag=$(escape_sed_pat "$current_tag")
        _pat="${safe_action}@${safe_current_tag}"
        # The replacement side does not need pattern escaping for the action
        # ref because sed replacements treat / as literal when the delimiter
        # is |. Keep the legacy `/` escape for clarity.
        _rep="${full_action//\//\\/}@${new_sha}  # ${safe_tag}"
        while IFS= read -r wf_file; do
            local tmp_wf
            tmp_wf=$(mktemp)
            # Match the action ref to end of line, dropping any existing
            # inline comment so the new "  # <tag>" replaces it cleanly.
            sed -E "s|${_pat}([[:space:]]+#.*)?[[:space:]]*$|${_rep}|g" "$wf_file" > "$tmp_wf"
            mv "$tmp_wf" "$wf_file"
        done < <(grep -rl "${full_action}@${current_tag}" "$WORKFLOWS_DIR"/ 2>/dev/null)
    done < "$CHANGE_LOG"

    echo -e "${GREEN}Done. Review with: git diff $WORKFLOWS_DIR${NC}"
}

# ---------------------------------------------------------------------------
# Extract unique pinned action references from all workflow files
# Pattern: uses: owner/repo[/subpath]@<40-char-sha>  # vX.Y.Z
# ---------------------------------------------------------------------------
# Register cleanup before either mode runs so pin_tags_main and the legacy
# flow share a single trap. Variables start empty; each mode assigns its
# own mktemp targets. The trap tolerates unset paths via :-.
UNIQUE_ACTIONS_FILE=""
CHANGE_LOG=""
# Use ${VAR:+"$VAR"} so the trap expands to nothing when the variable is
# empty. `rm -f ""` is a no-op on GNU coreutils but emits a warning on
# BSD rm (macOS), and a literal "" argument can confuse some shells.
trap 'rm -f ${UNIQUE_ACTIONS_FILE:+"$UNIQUE_ACTIONS_FILE"} ${CHANGE_LOG:+"$CHANGE_LOG"}' EXIT

if [[ "$PIN_TAGS" = true ]]; then
    pin_tags_main
    exit 0
fi

UNIQUE_ACTIONS_FILE=$(mktemp)
CHANGE_LOG=$(mktemp)

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
            "$full_action" "$current_sha" "$current_version" "$new_sha" "${latest_version//|/}" \
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
    _pat_ver="${current_version//./\\.}"
    _rep_ver="${latest_version//\\/\\\\}"; _rep_ver="${_rep_ver//&/\\&}"
    # Find every workflow file containing this action+sha and update it
    while IFS= read -r wf_file; do
        tmp_wf=$(mktemp)
        sed \
            "s|${full_action}@${current_sha}[[:space:]]*#[[:space:]]*${_pat_ver}|${full_action}@${new_sha}  # ${_rep_ver}|g" \
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
