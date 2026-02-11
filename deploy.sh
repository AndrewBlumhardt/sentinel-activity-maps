#!/bin/bash
set -e

# Sentinel Activity Maps - Automated Deployment Script (Bash)
# Compatible with Linux, macOS, and WSL

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
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
RESOURCE_GROUP_NAME=${RESOURCE_GROUP_NAME:-"rg-sentinel-activity-maps"}
LOCATION=${LOCATION:-"eastus"}
STORAGE_ACCOUNT_NAME=${STORAGE_ACCOUNT_NAME:-"sentinelactmaps$RANDOM"}
FUNCTION_APP_NAME=${FUNCTION_APP_NAME:-"sentinel-activity-maps-func-$RANDOM"}
WORKSPACE_ID=""
SUBSCRIPTION_ID=""
CLOUD="AzureCloud"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --resource-group)
            RESOURCE_GROUP_NAME="$2"
            shift 2
            ;;
        --location)
            LOCATION="$2"
            shift 2
            ;;
        --storage-account)
            STORAGE_ACCOUNT_NAME="$2"
            shift 2
            ;;
        --function-app)
            FUNCTION_APP_NAME="$2"
            shift 2
            ;;
        --workspace-id)
            WORKSPACE_ID="$2"
            shift 2
            ;;
        --subscription)
            SUBSCRIPTION_ID="$2"
            shift 2
            ;;
        --cloud)
            CLOUD="$2"
            shift 2
            ;;
        --help)
            echo "Usage: ./deploy.sh --workspace-id <WORKSPACE_ID> [OPTIONS]"
            echo ""
            echo "Required:"
            echo "  --workspace-id        Log Analytics Workspace ID (GUID)"
            echo ""
            echo "Optional:"
            echo "  --resource-group      Resource group name (default: rg-sentinel-activity-maps)"
            echo "  --location            Azure region (default: eastus)"
            echo "  --storage-account     Storage account name (3-24 chars, lowercase alphanumeric)"
            echo "                        Default: sentinelactmapsXXXXX"
            echo "  --function-app        Function app name (default: sentinel-activity-maps-func-XXXXX)"
            echo "  --subscription        Azure subscription ID"
            echo "  --cloud               Azure cloud (AzureCloud, AzureUSGovernment) default: AzureCloud"
            echo "  --help                Show this help message"
            echo ""
            echo "Examples:"
            echo "  ./deploy.sh --workspace-id 12345678-1234-1234-1234-123456789012"
            echo "  ./deploy.sh --workspace-id <ID> --cloud AzureUSGovernment"
            echo ""
            echo "Note: Requires Owner or Contributor role on subscription or target resource group"
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
if [ -z "$WORKSPACE_ID" ]; then
    print_error "Workspace ID is required. Use --workspace-id <WORKSPACE_ID>"
    echo "Use --help for usage information"
    exit 1
fi

# Validate workspace ID format
if ! [[ $WORKSPACE_ID =~ ^[0-9a-fA-F]{8}-([0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}$ ]]; then
    print_error "Invalid Workspace ID format. Expected GUID format."
    exit 1
fi

# Validate storage account name (must be lowercase, 3-24 chars, alphanumeric only)
if ! [[ $STORAGE_ACCOUNT_NAME =~ ^[a-z0-9]{3,24}$ ]]; then
    print_error "Invalid Storage Account name. Must be 3-24 characters, lowercase letters and numbers only."
    print_info "Current value: $STORAGE_ACCOUNT_NAME"
    exit 1
fi

# Check prerequisites
print_step "Checking prerequisites..."

# Check Azure CLI
if ! command -v az &> /dev/null; then
    print_error "Azure CLI not found. Please install: https://aka.ms/install-azure-cli"
    exit 1
fi

AZ_VERSION=$(az version --query '"azure-cli"' -o tsv)
print_success "Azure CLI version $AZ_VERSION"

# Check if logged in
print_step "Checking Azure login..."
print_info "Required: Owner or Contributor role on subscription or target resource group"

if ! az account show &> /dev/null; then
    print_info "Not logged in. Starting login to $CLOUD..."
    if [ "$CLOUD" == "AzureUSGovernment" ]; then
        az cloud set --name AzureUSGovernment
        print_info "Switched to Azure US Government cloud"
    fi
    az login
else
    # Verify we're in the correct cloud
    CURRENT_CLOUD=$(az cloud show --query name -o tsv)
    if [ "$CURRENT_CLOUD" != "$CLOUD" ]; then
        print_info "Switching to $CLOUD..."
        az cloud set --name "$CLOUD"
        az login
    fi
fi

ACCOUNT_USER=$(az account show --query user.name -o tsv)
print_success "Logged in as: $ACCOUNT_USER"
print_success "Cloud: $CLOUD"

# Set subscription if specified
if [ -n "$SUBSCRIPTION_ID" ]; then
    print_step "Setting subscription to $SUBSCRIPTION_ID..."
    az account set --subscription "$SUBSCRIPTION_ID"
    print_success "Subscription set"
else
    CURRENT_SUB=$(az account show --query name -o tsv)
    print_info "Using current subscription: $CURRENT_SUB"
fi

# Display deployment plan
echo -e "\n${MAGENTA}================================================${NC}"
echo -e "${MAGENTA}Deployment Plan${NC}"
echo -e "${MAGENTA}================================================${NC}"
echo "Resource Group:    $RESOURCE_GROUP_NAME"
echo "Location:          $LOCATION"
echo "Storage Account:   $STORAGE_ACCOUNT_NAME"
echo "Function App:      $FUNCTION_APP_NAME"
echo "Workspace ID:      $WORKSPACE_ID"
echo -e "${MAGENTA}================================================${NC}\n"

read -p "Proceed with deployment? (yes/no): " CONFIRMATION
if [ "$CONFIRMATION" != "yes" ]; then
    print_info "Deployment cancelled."
    exit 0
fi

# Start deployment
START_TIME=$(date +%s)

# 1. Create or Verify Resource Group
print_step "Checking resource group..."
RG_EXISTS=$(az group exists --name "$RESOURCE_GROUP_NAME")

if [ "$RG_EXISTS" == "true" ]; then
    print_info "Resource group already exists: $RESOURCE_GROUP_NAME"
    RG_LOCATION=$(az group show --name "$RESOURCE_GROUP_NAME" --query location -o tsv)
    print_info "Location: $RG_LOCATION"
else
    print_info "Creating new resource group..."
    az group create \
        --name "$RESOURCE_GROUP_NAME" \
        --location "$LOCATION" \
        --output none
    print_success "Resource group created: $RESOURCE_GROUP_NAME"
fi

# 2. Create or Verify Storage Account
print_step "Checking storage account..."
STORAGE_CHECK=$(az storage account check-name --name "$STORAGE_ACCOUNT_NAME" --query "nameAvailable" -o tsv)

if [ "$STORAGE_CHECK" == "false" ]; then
    print_info "Storage account name already in use: $STORAGE_ACCOUNT_NAME"
    # Verify it's in our resource group
    if az storage account show --name "$STORAGE_ACCOUNT_NAME" --resource-group "$RESOURCE_GROUP_NAME" &> /dev/null; then
        print_success "Using existing storage account in resource group"
    else
        print_error "Storage account '$STORAGE_ACCOUNT_NAME' exists but not in resource group '$RESOURCE_GROUP_NAME'"
        exit 1
    fi
else
    print_info "Creating new storage account..."
    az storage account create \
        --name "$STORAGE_ACCOUNT_NAME" \
        --resource-group "$RESOURCE_GROUP_NAME" \
        --location "$LOCATION" \
        --sku Standard_LRS \
        --kind StorageV2 \
        --allow-blob-public-access false \
        --min-tls-version TLS1_2 \
        --output none
    print_success "Storage account created: $STORAGE_ACCOUNT_NAME"
fi

# 3. Create Blob Containers
print_step "Creating blob containers..."

STORAGE_KEY=$(az storage account keys list \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --account-name "$STORAGE_ACCOUNT_NAME" \
    --query '[0].value' \
    --output tsv)

az storage container create \
    --name datasets \
    --account-name "$STORAGE_ACCOUNT_NAME" \
    --account-key "$STORAGE_KEY" \
    --output none

az storage container create \
    --name locks \
    --account-name "$STORAGE_ACCOUNT_NAME" \
    --account-key "$STORAGE_KEY" \
    --output none

print_success "Containers created: datasets, locks"

# 4. Create Function App
print_step "Creating Function App..."

# Check if function app already exists
if az functionapp show --name "$FUNCTION_APP_NAME" --resource-group "$RESOURCE_GROUP_NAME" &> /dev/null; then
    print_info "Function app already exists: $FUNCTION_APP_NAME"
    print_info "Skipping creation, will update configuration..."
else
    print_info "Creating new function app with consumption plan..."
    
    # Create Function App with consumption plan (no separate plan needed for consumption)
    az functionapp create \
        --resource-group "$RESOURCE_GROUP_NAME" \
        --name "$FUNCTION_APP_NAME" \
        --storage-account "$STORAGE_ACCOUNT_NAME" \
        --consumption-plan-location "$LOCATION" \
        --runtime python \
        --runtime-version 3.11 \
        --functions-version 4 \
        --os-type Linux \
        --disable-app-insights false \
        --output none
    
    print_success "Function App created: $FUNCTION_APP_NAME"
fi

# Enable managed identity if not already enabled
print_info "Ensuring managed identity is enabled..."
az functionapp identity assign \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --name "$FUNCTION_APP_NAME" \
    --output none 2>/dev/null || true

print_success "Managed identity configured"

# 5. Configure App Settings
print_step "Configuring application settings..."

STORAGE_URL="https://$STORAGE_ACCOUNT_NAME.blob.core.windows.net"

az functionapp config appsettings set \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --name "$FUNCTION_APP_NAME" \
    --settings \
        LOG_ANALYTICS_WORKSPACE_ID="$WORKSPACE_ID" \
        STORAGE_ACCOUNT_URL="$STORAGE_URL" \
        STORAGE_CONTAINER_DATASETS=datasets \
        STORAGE_CONTAINER_LOCKS=locks \
        DEFAULT_REFRESH_INTERVAL_SECONDS=300 \
        DEFAULT_QUERY_TIME_WINDOW_HOURS=24 \
        INCREMENTAL_OVERLAP_MINUTES=10 \
    --output none

print_success "Application settings configured"

# 6. Get Managed Identity Principal ID
print_step "Configuring managed identity..."

PRINCIPAL_ID=$(az functionapp identity show \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --name "$FUNCTION_APP_NAME" \
    --query principalId \
    --output tsv)

print_success "Managed Identity Principal ID: $PRINCIPAL_ID"

# 7. Assign RBAC Roles
print_step "Assigning RBAC roles..."

STORAGE_ACCOUNT_ID=$(az storage account show \
    --name "$STORAGE_ACCOUNT_NAME" \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --query id \
    --output tsv)

az role assignment create \
    --assignee "$PRINCIPAL_ID" \
    --role "Storage Blob Data Contributor" \
    --scope "$STORAGE_ACCOUNT_ID" \
    --output none

print_success "Assigned Storage Blob Data Contributor role"

print_info "Note: You may need to manually assign 'Log Analytics Reader' role to the Function App's managed identity on your Log Analytics Workspace"
print_info "Principal ID: $PRINCIPAL_ID"

# 8. Deploy Function Code
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
cp function_app.py "$BUILD_DIR/"
cp host.json "$BUILD_DIR/"
cp requirements.txt "$BUILD_DIR/"
cp sources.yaml "$BUILD_DIR/"
cp -r shared "$BUILD_DIR/"

# Create zip file
ZIP_PATH=$(mktemp).zip

cd "$BUILD_DIR"
zip -r "$ZIP_PATH" . > /dev/null

# Deploy zip
az functionapp deployment source config-zip \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --name "$FUNCTION_APP_NAME" \
    --src "$ZIP_PATH" \
    --output none

cd - > /dev/null

print_success "Function deployed successfully"

# 9. Summary
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
MINUTES=$((DURATION / 60))
SECONDS=$((DURATION % 60))

echo -e "\n${GREEN}================================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${GREEN}================================================${NC}"
echo "Duration:          ${MINUTES}m ${SECONDS}s"
echo "Resource Group:    $RESOURCE_GROUP_NAME"
echo "Function App:      $FUNCTION_APP_NAME"
echo "Storage Account:   $STORAGE_ACCOUNT_NAME"
echo ""
echo "Function Endpoints:"
echo "  Health:  https://$FUNCTION_APP_NAME.azurewebsites.net/api/health"
echo "  Refresh: https://$FUNCTION_APP_NAME.azurewebsites.net/api/refresh"
echo -e "${GREEN}================================================${NC}"

echo -e "\n${YELLOW}⚠️  Important Next Steps:${NC}"
echo -e "${YELLOW}1. Assign 'Log Analytics Reader' role to the Function App on your Log Analytics Workspace${NC}"
echo "   Principal ID: $PRINCIPAL_ID"
echo ""
echo -e "   ${CYAN}Option A - Via Function App Identity (Easiest):${NC}"
echo "   1. Go to Azure Portal → Function App '$FUNCTION_APP_NAME'"
echo "   2. Click 'Identity' in the left menu"
echo "   3. Go to 'Azure role assignments' tab"
echo "   4. Click '+ Add role assignment'"
echo "   5. Scope: Select your Log Analytics Workspace"
echo "   6. Role: Select 'Log Analytics Reader'"
echo "   7. Click 'Save'"
echo ""
echo -e "   ${CYAN}Option B - Azure CLI:${NC}"
echo "   az role assignment create --assignee $PRINCIPAL_ID --role 'Log Analytics Reader' --scope /subscriptions/<sub-id>/resourceGroups/<workspace-rg>/providers/Microsoft.OperationalInsights/workspaces/<workspace-name>"
echo ""
echo -e "${YELLOW}2. Test the deployment:${NC}"
echo -e "   ${CYAN}curl https://$FUNCTION_APP_NAME.azurewebsites.net/api/health${NC}"
echo ""
echo -e "${YELLOW}3. Trigger a data refresh:${NC}"
echo -e "   ${CYAN}curl -X POST https://$FUNCTION_APP_NAME.azurewebsites.net/api/refresh${NC}"

echo -e "\n${GREEN}✓ Deployment script completed successfully!${NC}"
