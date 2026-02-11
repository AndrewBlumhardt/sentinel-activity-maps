#!/bin/bash
set -e

# Sentinel Activity Maps - Code Update Script
# Deploys updated code to existing Function App

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

function print_step() {
    echo -e "\n${CYAN}✓ $1${NC}"
}

function print_success() {
    echo -e "  ${GREEN}✓ $1${NC}"
}

function print_error() {
    echo -e "  ${RED}✗ $1${NC}"
}

function print_info() {
    echo -e "  ${YELLOW}ℹ $1${NC}"
}

# Default values
FUNCTION_APP_NAME=""
RESOURCE_GROUP_NAME="rg-sentinel-activity-maps"
CLOUD="AzureCloud"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --function-app)
            FUNCTION_APP_NAME="$2"
            shift 2
            ;;
        --resource-group)
            RESOURCE_GROUP_NAME="$2"
            shift 2
            ;;
        --cloud)
            CLOUD="$2"
            shift 2
            ;;
        --help)
            echo "Usage: ./update-function.sh --function-app <FUNCTION_APP_NAME> [OPTIONS]"
            echo ""
            echo "Required:"
            echo "  --function-app        Name of the existing Function App"
            echo ""
            echo "Optional:"
            echo "  --resource-group      Resource group name (default: rg-sentinel-activity-maps)"
            echo "  --cloud               Azure cloud (AzureCloud, AzureUSGovernment)"
            echo "  --help                Show this help message"
            echo ""
            echo "Example:"
            echo "  ./update-function.sh --function-app sentinel-activity-maps-func-12345"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Validate required parameters
if [ -z "$FUNCTION_APP_NAME" ]; then
    print_error "Function App name is required. Use --function-app <NAME>"
    echo "Use --help for usage information"
    exit 1
fi

# Check Azure CLI
print_step "Checking prerequisites..."
if ! command -v az &> /dev/null; then
    print_error "Azure CLI not found. Please install: https://aka.ms/install-azure-cli"
    exit 1
fi

AZ_VERSION=$(az version --query '"azure-cli"' -o tsv)
print_success "Azure CLI version $AZ_VERSION"

# Check login
print_step "Checking Azure login..."
if ! az account show &> /dev/null; then
    print_info "Not logged in. Starting login to $CLOUD..."
    if [ "$CLOUD" == "AzureUSGovernment" ]; then
        az cloud set --name AzureUSGovernment
    fi
    az login
else
    # Verify cloud
    CURRENT_CLOUD=$(az cloud show --query name -o tsv)
    if [ "$CURRENT_CLOUD" != "$CLOUD" ]; then
        print_info "Switching to $CLOUD..."
        az cloud set --name "$CLOUD"
        az login
    fi
fi

ACCOUNT_USER=$(az account show --query user.name -o tsv)
print_success "Logged in as: $ACCOUNT_USER"

# Verify function app exists
print_step "Verifying Function App exists..."
if ! az functionapp show --name "$FUNCTION_APP_NAME" --resource-group "$RESOURCE_GROUP_NAME" &> /dev/null; then
    print_error "Function App '$FUNCTION_APP_NAME' not found in resource group '$RESOURCE_GROUP_NAME'"
    print_info "Available Function Apps in resource group:"
    az functionapp list --resource-group "$RESOURCE_GROUP_NAME" --query "[].name" -o tsv
    exit 1
fi

FUNC_LOCATION=$(az functionapp show --name "$FUNCTION_APP_NAME" --resource-group "$RESOURCE_GROUP_NAME" --query location -o tsv)
print_success "Found Function App: $FUNCTION_APP_NAME"
print_info "Location: $FUNC_LOCATION"

# Start deployment
START_TIME=$(date +%s)

print_step "Deploying function code..."

# Determine API directory
if [ -f "function_app.py" ]; then
    API_PATH="."
elif [ -f "api/function_app.py" ]; then
    API_PATH="api"
else
    print_error "Cannot find function_app.py. Please run from project root or api directory."
    exit 1
fi

cd "$API_PATH"

# Create temporary build directory
BUILD_DIR=$(mktemp -d)
trap "rm -rf $BUILD_DIR" EXIT

# Copy necessary files
print_info "Packaging function code..."
cp function_app.py "$BUILD_DIR/"
cp host.json "$BUILD_DIR/"
cp requirements.txt "$BUILD_DIR/"
cp sources.yaml "$BUILD_DIR/"
cp -r shared "$BUILD_DIR/"

# Create zip file
ZIP_PATH=$(mktemp).zip

cd "$BUILD_DIR"
zip -r "$ZIP_PATH" . > /dev/null

cd - > /dev/null

# Deploy zip
print_info "Uploading to Azure..."
az functionapp deployment source config-zip \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --name "$FUNCTION_APP_NAME" \
    --src "$ZIP_PATH" \
    --output none

print_success "Function deployed successfully"

# Restart function app
print_step "Restarting Function App..."
az functionapp restart --name "$FUNCTION_APP_NAME" --resource-group "$RESOURCE_GROUP_NAME" --output none
print_success "Function App restarted"

# Summary
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
MINUTES=$((DURATION / 60))
SECONDS=$((DURATION % 60))

echo -e "\n${GREEN}================================================${NC}"
echo -e "${GREEN}Code Update Complete!${NC}"
echo -e "${GREEN}================================================${NC}"
echo "Duration:       ${MINUTES}m ${SECONDS}s"
echo "Function App:   $FUNCTION_APP_NAME"
echo ""
echo "Endpoints:"
echo "  Health:  https://$FUNCTION_APP_NAME.azurewebsites.net/api/health"
echo "  Refresh: https://$FUNCTION_APP_NAME.azurewebsites.net/api/refresh"
echo -e "${GREEN}================================================${NC}"

echo -e "\n${CYAN}ℹ️  Testing the deployment:${NC}"
echo "  curl https://$FUNCTION_APP_NAME.azurewebsites.net/api/health"
echo ""
echo -e "${YELLOW}Note: It may take 30-60 seconds for the function to be fully ready.${NC}"

echo -e "\n${GREEN}✓ Code update completed successfully!${NC}"
