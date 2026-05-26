#!/usr/bin/env bash
# =============================================================================
# Fleet-wide SHA-pin audit
# =============================================================================
# For every repo in the specified org(s), reads each .github/workflows/*.yml
# via the GitHub API and counts references whose owner is NOT in the
# --skip-owners list (default: ByronWilliamsCPA,williaby) and whose ref is a
# tag (@v...) or branch (@main/@master/@HEAD/@develop).
#
# Output: CSV with one row per repo. Each row is one of:
#   {repo},{count}   numeric violations found
#   {repo},error     API call failed (rate limit, 5xx, auth loss); diagnostic
#                    message written to stderr
# Exit code: 0 even when violations or errors are present (this is a report,
# not a gate). Errors are surfaced via the sentinel row plus stderr.
#
# Environment overrides:
#   REPO_LIMIT     Max repos fetched per org via `gh repo list` (default 1000).
#                  Lower it for testing; raise it if your fleet exceeds 1000
#                  repos. The script emits a stderr WARN when the result count
#                  equals REPO_LIMIT (saturation, audit may be truncated).
#   STRICT_AUDIT   When set to "1", exit non-zero at the end of the run if any
#                  API failure produced a `repo,error` row OR any org's repo
#                  count saturated REPO_LIMIT. Use this in CI gates that
#                  should fail closed when the audit is incomplete. The
#                  default (unset / "0") preserves report-only semantics.
#
# Usage:
#   ./scripts/fleet-audit-sha-pins.sh --org ByronWilliamsCPA [--org williaby] \
#     [--skip-owners ByronWilliamsCPA,williaby] [--output audit.csv]
#   STRICT_AUDIT=1 ./scripts/fleet-audit-sha-pins.sh --org ByronWilliamsCPA
#   REPO_LIMIT=3 ./scripts/fleet-audit-sha-pins.sh --org ByronWilliamsCPA
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

# gh_api_safe ENDPOINT JQ_FILTER
# Wraps a `gh api` call so that 404 (legitimate "no workflows directory")
# is distinguishable from real failures (rate limit, 5xx, auth loss).
# Sets two globals:
#   GH_API_STATUS = "ok" | "missing" | "error"
#   GH_API_BODY   = body on ok/missing-as-empty, error message on error
gh_api_safe() {
    local endpoint="$1"
    local jq_filter="$2"
    local raw rc
    raw=$(gh api "$endpoint" --jq "$jq_filter" 2>&1)
    rc=$?
    if [[ $rc -eq 0 ]]; then
        GH_API_STATUS="ok"
        GH_API_BODY="$raw"
        return 0
    fi
    # gh prints messages like "gh: Not Found (HTTP 404)" on stderr; we
    # captured them via 2>&1 so they live in $raw. Anchor on the exact
    # "(HTTP 404)" parenthesized form rather than the broader "Not Found"
    # substring so a 5xx response or upstream proxy page that happens to
    # contain "Not Found" cannot be misclassified as a missing resource.
    if [[ "$raw" == *"(HTTP 404)"* ]]; then
        GH_API_STATUS="missing"
        GH_API_BODY=""
        return 0
    fi
    GH_API_STATUS="error"
    GH_API_BODY="$raw"
    return 1
}

# is_skipped_owner OWNER -- literal-match, no regex injection.
is_skipped_owner() {
    case ",${SKIP_OWNERS}," in
        *,"$1",*) return 0 ;;
        *)        return 1 ;;
    esac
}

# REPO_LIMIT defaults to 1000 but may be overridden via environment for tests
# and for fleets that grow beyond the default.
REPO_LIMIT="${REPO_LIMIT:-1000}"

# Tracks whether the audit was incomplete due to API errors or saturation;
# STRICT_AUDIT consults this at exit to decide whether to fail closed.
audit_incomplete=false

for org in "${ORGS[@]}"; do
    mapfile -t repos < <(gh repo list "$org" --limit "$REPO_LIMIT" --json name --jq '.[].name')
    if [[ ${#repos[@]} -eq $REPO_LIMIT ]]; then
        echo "WARN: $org returned exactly $REPO_LIMIT repos; audit may be truncated. Raise REPO_LIMIT or page through results." >&2
        audit_incomplete=true
    fi
    for repo in "${repos[@]}"; do
        full="$org/$repo"
        # Skip infrastructure meta-repos
        case "$full" in
            ByronWilliamsCPA/.github|ByronWilliamsCPA/.claude|williaby/.github|williaby/.claude) continue ;;
        esac

        if ! gh_api_safe "repos/$full/contents/.github/workflows" '.[].path'; then
            echo "WARN: $full: workflows listing failed: $GH_API_BODY" >&2
            emit "$full,error"
            continue
        fi
        if [[ "$GH_API_STATUS" == "missing" ]] || [[ -z "$GH_API_BODY" ]]; then
            emit "$full,0"
            continue
        fi
        files="$GH_API_BODY"

        violations=0
        api_error=false
        while IFS= read -r path; do
            [[ -z "$path" ]] && continue
            [[ "$path" != *.yml && "$path" != *.yaml ]] && continue
            if ! gh_api_safe "repos/$full/contents/$path" '.content'; then
                echo "WARN: $full:$path: content fetch failed: $GH_API_BODY" >&2
                api_error=true
                break
            fi
            if [[ "$GH_API_STATUS" == "missing" ]]; then
                # The directory listing returned this path but the file
                # fetch returned 404. This is a race (file deleted between
                # calls) or a token-scope mismatch. Log but do not flip the
                # repo to error: the listing was authoritative, this single
                # file is the anomaly.
                echo "WARN: $full:$path: listed but 404 on fetch (race or auth scope?)" >&2
                continue
            fi
            if ! content=$(echo "$GH_API_BODY" | base64 -d 2>/dev/null); then
                echo "WARN: $full:$path: base64 decode failed" >&2
                api_error=true
                break
            fi
            [[ -z "$content" ]] && continue
            while IFS= read -r line; do
                # Skip comment lines
                [[ "$line" =~ ^[[:space:]]*# ]] && continue
                if [[ "$line" =~ $TAG_OR_BRANCH_RE ]]; then
                    owner="${BASH_REMATCH[2]}"
                    ref="${BASH_REMATCH[4]}"
                    # Skip if owner is in the skip list
                    if is_skipped_owner "$owner"; then
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

        if [[ "$api_error" == true ]]; then
            emit "$full,error"
            audit_incomplete=true
        else
            emit "$full,$violations"
        fi
    done
done

# Fail closed when running under STRICT_AUDIT=1. The default flow remains
# report-only (exit 0) so existing CI consumers do not break.
if [[ "${STRICT_AUDIT:-0}" == "1" && "$audit_incomplete" == true ]]; then
    echo "ERROR: STRICT_AUDIT=1 and the audit was incomplete (API errors and/or REPO_LIMIT saturation). Exiting non-zero." >&2
    exit 2
fi
