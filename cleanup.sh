#!/bin/bash
set -e

# Sentinel Activity Maps - Cleanup Script
# Removes all Azure resources

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

function print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

function print_info() {
    echo -e "${CYAN}ℹ  $1${NC}"
}

function print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

function print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Default values
RESOURCE_GROUP_NAME=${RESOURCE_GROUP_NAME:-"rg-sentinel-activity-maps"}
FORCE=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --resource-group)
            RESOURCE_GROUP_NAME="$2"
            shift 2
            ;;
        --force)
            FORCE=true
            shift
            ;;
        --help)
            echo "Usage: ./cleanup.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --resource-group      Resource group name (default: rg-sentinel-activity-maps)"
            echo "  --force               Skip confirmation prompt"
            echo "  --help                Show this help message"
            echo ""
            echo "Example:"
            echo "  ./cleanup.sh --resource-group rg-sentinel-activity-maps"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Check Azure CLI
if ! command -v az &> /dev/null; then
    print_error "Azure CLI not found. Please install: https://aka.ms/install-azure-cli"
    exit 1
fi

# Check if logged in
if ! az account show &> /dev/null; then
    print_error "Not logged in to Azure. Run 'az login' first."
    exit 1
fi

ACCOUNT_USER=$(az account show --query user.name -o tsv)
ACCOUNT_SUB=$(az account show --query name -o tsv)

print_info "Logged in as: $ACCOUNT_USER"
print_info "Subscription: $ACCOUNT_SUB"

# Check if resource group exists
echo ""
echo "Checking for resource group: $RESOURCE_GROUP_NAME..."
RG_EXISTS=$(az group exists --name "$RESOURCE_GROUP_NAME")

if [ "$RG_EXISTS" == "false" ]; then
    print_warning "Resource group '$RESOURCE_GROUP_NAME' does not exist."
    exit 0
fi

# List resources in the group
echo ""
echo "Resources to be deleted:"
echo "========================"

RESOURCES=$(az resource list --resource-group "$RESOURCE_GROUP_NAME" --query "[].{name:name, type:type}" -o tsv)
RESOURCE_COUNT=$(echo "$RESOURCES" | wc -l)

if [ -z "$RESOURCES" ]; then
    print_info "No resources found in resource group."
    RESOURCE_COUNT=0
else
    while IFS=$'\t' read -r name type; do
        echo -e "  ${YELLOW}- $name ($type)${NC}"
    done <<< "$RESOURCES"
fi

echo "========================"
echo -e "${RED}Resource Group: $RESOURCE_GROUP_NAME${NC}"
echo -e "${RED}Total Resources: $RESOURCE_COUNT${NC}"
echo "========================"
echo ""

# Confirmation
if [ "$FORCE" != "true" ]; then
    print_warning "This will permanently delete ALL resources in the resource group."
    print_warning "This action cannot be undone!"
    echo ""
    read -p "Type 'DELETE' to confirm: " CONFIRMATION
    
    if [ "$CONFIRMATION" != "DELETE" ]; then
        print_info "Cleanup cancelled."
        exit 0
    fi
fi

# Start deletion
echo ""
print_info "Deleting resource group..."
START_TIME=$(date +%s)

az group delete \
    --name "$RESOURCE_GROUP_NAME" \
    --yes \
    --no-wait

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

print_success "Deletion initiated successfully."
print_info "Resources are being deleted in the background."
print_info "This may take several minutes to complete."

echo ""
echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}Cleanup Complete!${NC}"
echo -e "${GREEN}================================================${NC}"
echo "Resource Group: $RESOURCE_GROUP_NAME"
echo "Status:         Deletion in progress"
echo "Time taken:     ${DURATION}s"
echo -e "${GREEN}================================================${NC}"
echo ""

print_info "To check deletion status, run:"
echo -e "  ${CYAN}az group show --name $RESOURCE_GROUP_NAME${NC}"
