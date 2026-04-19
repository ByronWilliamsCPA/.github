#!/bin/bash
# transfer-repos.sh - Transfer repositories to organization
# Preserves all history, issues, PRs, stars, and releases

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}📦 Repository Transfer Tool${NC}"
echo "============================"
echo ""

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo -e "${RED}❌ GitHub CLI not found${NC}"
    echo ""
    echo "Install GitHub CLI:"
    echo "  macOS:  brew install gh"
    echo "  Linux:  sudo apt install gh"
    echo "  Other:  https://cli.github.com/manual/installation"
    exit 1
fi

# Check authentication
if ! gh auth status &> /dev/null; then
    echo -e "${YELLOW}⚠️  Not authenticated with GitHub${NC}"
    echo ""
    echo "Please authenticate:"
    echo "  gh auth login"
    echo ""
    exit 1
fi

# Get username
USERNAME=$(gh api user -q .login)
echo -e "📝 User: ${GREEN}$USERNAME${NC}"
echo ""

# Get organization
echo -e "${YELLOW}Available organizations:${NC}"
gh api user/orgs --jq '.[] | "  - \(.login)"'
echo ""

read -rp "Target organization name: " ORG_NAME
if [ -z "$ORG_NAME" ]; then
    echo -e "${RED}❌ Organization name required${NC}"
    exit 1
fi

# Verify organization exists and user has access
if ! gh api "orgs/$ORG_NAME" &> /dev/null; then
    echo -e "${RED}❌ Organization '$ORG_NAME' not found or no access${NC}"
    exit 1
fi

echo ""
echo "🔍 Finding Python repositories..."
REPOS=$(gh repo list "$USERNAME" --limit 100 --json name,primaryLanguage -q '.[] | select(.primaryLanguage.name == "Python") | .name')

if [ -z "$REPOS" ]; then
    echo -e "${RED}❌ No Python repositories found${NC}"
    exit 1
fi

# Convert to array
readarray -t REPO_ARRAY <<< "$REPOS"
echo -e "${GREEN}✅ Found ${#REPO_ARRAY[@]} Python repositories${NC}"
echo ""

echo -e "${YELLOW}📋 Repositories to transfer:${NC}"
for repo in "${REPO_ARRAY[@]}"; do
    echo "  - $USERNAME/$repo → $ORG_NAME/$repo"
done
echo ""

echo -e "${YELLOW}⚠️  Important Notes:${NC}"
echo "  • All history, issues, PRs, stars will be preserved"
echo "  • Collaborators will lose access (re-add via org teams)"
echo "  • GitHub redirects old URLs for 90+ days"
echo "  • You must be an owner of $ORG_NAME"
echo ""

read -rp "Transfer all repos listed above? (y/N): " CONFIRM_ALL
echo ""

SUCCESS=0
FAILED=0
SKIPPED=0
FAILED_REPOS=()

for repo in "${REPO_ARRAY[@]}"; do
    FULL_REPO="$USERNAME/$repo"

    # If not confirming all, ask individually
    if [[ ! $CONFIRM_ALL =~ ^[Yy]$ ]]; then
        read -rp "Transfer $repo? (y/N): " CONFIRM
        if [[ ! $CONFIRM =~ ^[Yy]$ ]]; then
            echo -e "  ${YELLOW}⏭️  Skipped${NC}"
            ((SKIPPED++))
            continue
        fi
    fi

    printf "  %-50s ... " "$repo"

    # Attempt transfer using GitHub API
    if gh api "repos/$FULL_REPO/transfer" -X POST -f new_owner="$ORG_NAME" &>/dev/null; then
        # Wait briefly and verify transfer completed
        sleep 1
        if gh api "repos/$ORG_NAME/$repo" &>/dev/null; then
            echo -e "${GREEN}✅${NC}"
            ((SUCCESS++))
        else
            echo -e "${RED}❌ (transfer initiated but verification failed)${NC}"
            ((FAILED++))
            FAILED_REPOS+=("$repo")
        fi
    else
        echo -e "${RED}❌${NC}"
        ((FAILED++))
        FAILED_REPOS+=("$repo")
    fi
done

echo ""
echo "============================"
echo -e "${GREEN}✅ Transferred: $SUCCESS/${#REPO_ARRAY[@]}${NC}"

if [ $SKIPPED -gt 0 ]; then
    echo -e "${YELLOW}⏭️  Skipped: $SKIPPED/${#REPO_ARRAY[@]}${NC}"
fi

if [ $FAILED -gt 0 ]; then
    echo -e "${RED}❌ Failed: $FAILED/${#REPO_ARRAY[@]}${NC}"
    echo ""
    echo "Failed repositories:"
    for repo in "${FAILED_REPOS[@]}"; do
        echo "  - $repo"
    done
    echo ""
    echo "Common reasons for failure:"
    echo "  • Repository name already exists in organization"
    echo "  • Insufficient permissions (must be org owner)"
    echo "  • Repository has GitHub Apps that prevent transfer"
fi

echo ""
echo -e "${BLUE}Done!${NC}"
echo ""

if [ $SUCCESS -gt 0 ]; then
    echo -e "${GREEN}Next steps:${NC}"
    echo "  1. Add organization-level secrets:"
    echo "     gh secret set QLTY_TOKEN --org $ORG_NAME --visibility all"
    echo ""
    echo "  2. Configure team access in organization settings"
    echo ""
    echo "  3. Update any CI/CD configs with new repo URLs"
fi
