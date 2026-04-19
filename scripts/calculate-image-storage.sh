#!/bin/bash
# =============================================================================
# Container Image Storage Calculator
# =============================================================================
# Calculates total storage used by container images to estimate GHCR costs
#
# Usage:
#   ./calculate-image-storage.sh [--all|--used|--local]
#
# Options:
#   --all     Show all images (default)
#   --used    Show only images currently used by running containers
#   --local   Scan local docker daemon
#   --repo    Scan repository docker-compose files
#
# GHCR Pricing (as of 2026):
#   - Public images: FREE (unlimited storage and bandwidth)
#   - Private images: FREE up to 500MB, then $0.25/GB/month
# =============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default mode
MODE="${1:---all}"

# Function to convert bytes to human-readable format
bytes_to_human() {
    local bytes=$1
    if (( bytes < 1024 )); then
        echo "${bytes}B"
    elif (( bytes < 1048576 )); then
        echo "$(awk "BEGIN {printf \"%.2f\", $bytes/1024}")KB"
    elif (( bytes < 1073741824 )); then
        echo "$(awk "BEGIN {printf \"%.2f\", $bytes/1048576}")MB"
    else
        echo "$(awk "BEGIN {printf \"%.2f\", $bytes/1073741824}")GB"
    fi
}

# Function to calculate GHCR cost
calculate_ghcr_cost() {
    local total_mb=$1
    local cost=0

    if (( $(echo "$total_mb > 500" | bc -l) )); then
        local billable_mb
        billable_mb=$(echo "$total_mb - 500" | bc -l)
        local billable_gb
        billable_gb=$(echo "$billable_mb / 1024" | bc -l)
        cost=$(echo "$billable_gb * 0.25" | bc -l)
    fi

    printf "%.2f" "$cost"
}

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║           Container Image Storage Calculator                        ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# =============================================================================
# Method 1: Scan Local Docker Daemon
# =============================================================================

if [[ "$MODE" == "--all" || "$MODE" == "--local" ]]; then
    echo -e "${YELLOW}📦 Scanning local Docker images...${NC}"
    echo ""

    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ Docker not found. Skipping local scan.${NC}"
    else
        # Get all images with sizes
        echo -e "${GREEN}All Images:${NC}"
        echo "─────────────────────────────────────────────────────────────────────────"
        printf "%-50s %15s %15s\n" "REPOSITORY:TAG" "SIZE" "VIRTUAL SIZE"
        echo "─────────────────────────────────────────────────────────────────────────"

        total_size=0
        image_count=0

        # Read docker images output
        while IFS= read -r line; do
            if [[ "$line" == "REPOSITORY"* ]]; then
                continue  # Skip header
            fi

            repo=$(echo "$line" | awk '{print $1}')
            tag=$(echo "$line" | awk '{print $2}')
            size=$(echo "$line" | awk '{print $7}')

            # Convert size to bytes for calculation
            size_bytes=0
            if [[ "$size" == *"GB"* ]]; then
                size_num="${size//GB/}"
                size_bytes=$(echo "$size_num * 1073741824" | bc -l | cut -d'.' -f1)
            elif [[ "$size" == *"MB"* ]]; then
                size_num="${size//MB/}"
                size_bytes=$(echo "$size_num * 1048576" | bc -l | cut -d'.' -f1)
            elif [[ "$size" == *"KB"* ]]; then
                size_num="${size//KB/}"
                size_bytes=$(echo "$size_num * 1024" | bc -l | cut -d'.' -f1)
            fi

            printf "%-50s %15s\n" "${repo}:${tag}" "$size"

            total_size=$((total_size + size_bytes))
            image_count=$((image_count + 1))
        done < <(docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}")

        echo "─────────────────────────────────────────────────────────────────────────"
        echo ""

        # Summary
        total_gb=$(echo "scale=2; $total_size / 1073741824" | bc -l)
        total_mb=$(echo "scale=2; $total_size / 1048576" | bc -l)

        echo -e "${GREEN}📊 Local Images Summary:${NC}"
        echo "  Total Images: $image_count"
        echo "  Total Size: $(bytes_to_human $total_size) (${total_gb}GB)"
        echo ""

        # GHCR Cost Calculation
        monthly_cost=$(calculate_ghcr_cost "$total_mb")

        echo -e "${BLUE}💰 GHCR Private Storage Cost Estimate:${NC}"
        echo "  Total Storage: ${total_mb}MB"

        if (( $(echo "$total_mb <= 500" | bc -l) )); then
            echo -e "  ${GREEN}✅ FREE (under 500MB)${NC}"
        else
            billable_mb=$(echo "$total_mb - 500" | bc -l)
            echo "  Free Tier: 500MB"
            echo "  Billable: ${billable_mb}MB"
            echo -e "  ${YELLOW}Monthly Cost: \$${monthly_cost}${NC}"

            yearly_cost=$(echo "$monthly_cost * 12" | bc -l)
            printf "  Yearly Cost: \$%.2f\n" "$yearly_cost"
        fi
        echo ""
    fi
fi

# =============================================================================
# Method 2: Scan Repository Docker Compose Files
# =============================================================================

if [[ "$MODE" == "--all" || "$MODE" == "--repo" ]]; then
    echo -e "${YELLOW}📄 Scanning repository docker-compose files...${NC}"
    echo ""

    # Find all docker-compose files
    compose_files=()
    if [ -d "services" ]; then
        while IFS= read -r file; do
            compose_files+=("$file")
        done < <(find services -name "docker-compose.yml" -o -name "docker-compose.yaml")
    fi

    if [ ${#compose_files[@]} -eq 0 ]; then
        echo -e "${YELLOW}⚠️  No docker-compose files found in services/ directory${NC}"
    else
        echo -e "${GREEN}Found ${#compose_files[@]} docker-compose files${NC}"
        echo ""

        # Extract unique images from compose files
        declare -A unique_images

        for file in "${compose_files[@]}"; do
            while IFS= read -r image; do
                # Skip variable substitutions and empty lines
                if [[ ! "$image" =~ \$\{ ]] && [ -n "$image" ]; then
                    unique_images["$image"]=1
                fi
            done < <(grep -oP '^\s*image:\s*\K[^\s#]+' "$file" || true)
        done

        echo -e "${GREEN}Unique images referenced in compose files:${NC}"
        echo "─────────────────────────────────────────────────────────────────────────"

        image_count=0
        for image in "${!unique_images[@]}"; do
            echo "  $image"
            image_count=$((image_count + 1))
        done

        echo "─────────────────────────────────────────────────────────────────────────"
        echo "  Total unique images: $image_count"
        echo ""

        # Categorize by registry
        echo -e "${GREEN}Images by registry:${NC}"

        dhi_count=0
        chainguard_count=0
        distroless_count=0
        dockerhub_count=0
        ghcr_count=0
        other_count=0

        for image in "${!unique_images[@]}"; do
            if [[ "$image" == dhi.io/* ]]; then
                dhi_count=$((dhi_count + 1))
            elif [[ "$image" == cgr.dev/* ]]; then
                chainguard_count=$((chainguard_count + 1))
            elif [[ "$image" == gcr.io/distroless/* ]]; then
                distroless_count=$((distroless_count + 1))
            elif [[ "$image" == ghcr.io/* ]]; then
                ghcr_count=$((ghcr_count + 1))
            elif [[ "$image" == */* ]] && [[ "$image" != *:*/* ]]; then
                dockerhub_count=$((dockerhub_count + 1))
            else
                other_count=$((other_count + 1))
            fi
        done

        echo "  dhi.io (Docker Hardened Images): $dhi_count"
        echo "  cgr.dev (Chainguard): $chainguard_count"
        echo "  gcr.io/distroless (Google): $distroless_count"
        echo "  ghcr.io (GitHub CR): $ghcr_count"
        echo "  Docker Hub: $dockerhub_count"
        echo "  Other registries: $other_count"
        echo ""
    fi
fi

# =============================================================================
# GHCR Pricing Information
# =============================================================================

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                  GHCR Pricing Reference (2026)                       ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}Public Images:${NC}"
echo "  ✅ FREE - Unlimited storage and bandwidth"
echo ""
echo -e "${YELLOW}Private Images:${NC}"
echo "  ✅ FREE - Up to 500MB storage"
echo "  💰 \$0.25/GB/month - Over 500MB"
echo ""
echo -e "${BLUE}Bandwidth (for private images):${NC}"
echo "  ✅ FREE - Up to 1GB/month"
echo "  💰 \$0.50/GB - Over 1GB/month"
echo ""
echo -e "${GREEN}💡 Recommendation:${NC}"
echo "  • Use public images in GHCR when possible (FREE)"
echo "  • Mirror hardened images (dhi.io, cgr.dev) to public GHCR repos"
echo "  • Only use private repos for proprietary application images"
echo ""
echo -e "${YELLOW}📊 Based on your current images:${NC}"
if [ -n "${total_mb:-}" ]; then
    images_to_mirror=$((dhi_count + chainguard_count + distroless_count))
    echo "  • Images to mirror to GHCR: ~${images_to_mirror}"
    echo "  • Recommended: Use PUBLIC GHCR repos (FREE)"
    echo "  • Current local storage: ${total_mb}MB"

    if (( $(echo "$total_mb > 500" | bc -l) )); then
        echo -e "  • ${YELLOW}If stored privately: \$${monthly_cost}/month${NC}"
        echo -e "  • ${GREEN}If stored publicly: \$0.00/month (FREE)${NC} ⭐"
    else
        echo -e "  • ${GREEN}✅ Within FREE tier for private storage${NC}"
    fi
fi
echo ""

# =============================================================================
# Recommendations
# =============================================================================

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                         Recommendations                              ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}1. Mirror Strategy:${NC}"
echo "   • Create PUBLIC repos in GHCR for base images (FREE)"
echo "   • Example: ghcr.io/yourusername/dhi-python:3.12 (public)"
echo ""
echo -e "${GREEN}2. Weekly Sync Workflow:${NC}"
echo "   • Auto-sync from dhi.io → ghcr.io (public)"
echo "   • Auto-sync from cgr.dev → ghcr.io (public)"
echo "   • Auto-sync from gcr.io → ghcr.io (public)"
echo ""
echo -e "${GREEN}3. Cost Savings:${NC}"
if [ -n "${monthly_cost:-}" ] && (( $(echo "$monthly_cost > 0" | bc -l) )); then
    yearly_savings=$(echo "$monthly_cost * 12" | bc -l)
    printf "   • Potential annual savings: \$%.2f (using public vs private)\n" "$yearly_savings"
fi
echo "   • Use public repos = \$0 storage costs"
echo "   • Use private repos = potential costs for >500MB"
echo ""

exit 0
