#Requires -Version 7.0
<#
.SYNOPSIS
    Automated deployment script for Sentinel Activity Maps Azure Function

.DESCRIPTION
    This script creates all required Azure resources and deploys the function app:
    - Resource Group
    - Storage Account with containers
    - Function App (Python 3.11, Linux)
    - Managed Identity configuration
    - RBAC role assignments
    - Function deployment

.PARAMETER ResourceGroupName
    Name of the resource group to create (default: rg-sentinel-activity-maps)

.PARAMETER Location
    Azure region for resources (default: eastus)

.PARAMETER StorageAccountName
    Storage account name (must be globally unique, lowercase, 3-24 chars, alphanumeric only)
    Default: sentinelactmapsXXXXX (random 5-digit suffix)

.PARAMETER FunctionAppName
    Function app name (must be globally unique, default: sentinel-activity-maps-func-XXXXX)

.PARAMETER WorkspaceId
    Log Analytics Workspace ID (required for function to work)

.PARAMETER SubscriptionId
    Azure subscription ID (uses current subscription if not specified)

.PARAMETER Cloud
    Azure cloud environment (AzureCloud, AzureUSGovernment)
    Default: AzureCloud (Commercial)
    AzureUSGovernment supports both GCC and GCC-High

.EXAMPLE
    .\deploy.ps1 -WorkspaceId "12345678-1234-1234-1234-123456789012"

.EXAMPLE
    .\deploy.ps1 -ResourceGroupName "rg-sentinel-activity-maps" -Location "westus2" -WorkspaceId "12345678-1234-1234-1234-123456789012"

.EXAMPLE
    .\deploy.ps1 -WorkspaceId "12345678-1234-1234-1234-123456789012" -Cloud AzureUSGovernment

.NOTES
    Requires Owner or Contributor role on the subscription or target resource group
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$false)]
    [string]$ResourceGroupName = "rg-sentinel-activity-maps",
    
    [Parameter(Mandatory=$false)]
    [string]$Location = "eastus",
    
    [Parameter(Mandatory=$false)]
    [string]$StorageAccountName = "sentinelactmaps$(Get-Random -Minimum 10000 -Maximum 99999)",
    
    [Parameter(Mandatory=$false)]
    [string]$FunctionAppName = "sentinel-activity-maps-func-$(Get-Random -Minimum 10000 -Maximum 99999)",
    
    [Parameter(Mandatory=$true)]
    [string]$WorkspaceId,
    
    [Parameter(Mandatory=$false)]
    [string]$SubscriptionId,
    
    [Parameter(Mandatory=$false)]
    [ValidateSet("AzureCloud", "AzureUSGovernment")]
    [string]$Cloud = "AzureCloud",
    
    [Parameter(Mandatory=$false)]
    [string]$MaxMindLicenseKey,
    
    [Parameter(Mandatory=$false)]
    [string]$KeyVaultName = "kv-sentinel-maps-$(Get-Random -Minimum 1000 -Maximum 9999)",
    
    [Parameter(Mandatory=$false)]
    [string]$StaticWebAppName = "swa-sentinel-activity-maps",
    
    [Parameter(Mandatory=$false)]
    [string]$AzureMapsAccountName = "maps-sentinel-activity-$(Get-Random -Minimum 1000 -Maximum 9999)",
    
    [Parameter(Mandatory=$false)]
    [switch]$SkipInfrastructure,
    
    [Parameter(Mandatory=$false)]
    [switch]$SkipFunctionApp
)

$ErrorActionPreference = "Stop"

# Color output functions
function Write-Step {
    param([string]$Message)
    Write-Host "`n✓ $Message" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "  ✓ $Message" -ForegroundColor Green
}

function Write-Error {
    param([string]$Message)
    Write-Host "  ✗ $Message" -ForegroundColor Red
}

function Write-Info {
    param([string]$Message)
    Write-Host "  ℹ $Message" -ForegroundColor Yellow
}

# Check prerequisites
Write-Step "Checking prerequisites..."

# Check Azure CLI
try {
    $azVersion = az version --output json 2>$null | ConvertFrom-Json
    Write-Success "Azure CLI version $($azVersion.'azure-cli')"
} catch {
    Write-Error "Azure CLI not found. Please install: https://aka.ms/install-azure-cli"
    exit 1
}

# Check Azure Functions Core Tools
try {
    $funcVersion = func --version 2>$null
    Write-Success "Azure Functions Core Tools version $funcVersion"
} catch {
    Write-Info "Azure Functions Core Tools not found (optional for deployment)"
}

# Login check with cloud support
Write-Step "Checking Azure login..."
Write-Info "Required: Owner or Contributor role on subscription or target resource group"

$account = az account show 2>$null | ConvertFrom-Json
if (-not $account) {
    Write-Info "Not logged in. Starting login to $Cloud..."
    if ($Cloud -eq "AzureUSGovernment") {
        az cloud set --name AzureUSGovernment
        Write-Info "Switched to Azure US Government cloud"
    }
    az login
    $account = az account show | ConvertFrom-Json
} else {
    # Verify we're in the correct cloud
    $currentCloud = az cloud show --query name -o tsv
    $targetCloud = if ($Cloud -eq "AzureUSGovernment") { "AzureUSGovernment" } else { "AzureCloud" }
    if ($currentCloud -ne $targetCloud) {
        Write-Info "Switching to $Cloud..."
        az cloud set --name $targetCloud
        az login
        $account = az account show | ConvertFrom-Json
    }
}

Write-Success "Logged in as: $($account.user.name)"
Write-Success "Cloud: $Cloud"

# Set subscription if specified
if ($SubscriptionId) {
    Write-Step "Setting subscription to $SubscriptionId..."
    az account set --subscription $SubscriptionId
    Write-Success "Subscription set"
} else {
    Write-Info "Using current subscription: $($account.name)"
}

# Validate workspace ID format
if ($WorkspaceId -notmatch '^[0-9a-fA-F]{8}-([0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}$') {
    Write-Error "Invalid Workspace ID format. Expected GUID format."
    exit 1
}

# Validate storage account name
if ($StorageAccountName -notmatch '^[a-z0-9]{3,24}$') {
    Write-Error "Invalid Storage Account name. Must be 3-24 characters, lowercase letters and numbers only."
    Write-Info "Current value: $StorageAccountName"
    exit 1
}

# Display deployment plan
Write-Host "`n================================================" -ForegroundColor Magenta
Write-Host "Deployment Plan" -ForegroundColor Magenta
Write-Host "================================================" -ForegroundColor Magenta
Write-Host "Resource Group:    $ResourceGroupName"
Write-Host "Location:          $Location"
Write-Host "Storage Account:   $StorageAccountName"
Write-Host "Function App:      $FunctionAppName"
Write-Host "Workspace ID:      $WorkspaceId"
Write-Host "================================================`n" -ForegroundColor Magenta

$confirmation = Read-Host "Proceed with deployment? (yes/no)"
if ($confirmation -ne "yes") {
    Write-Info "Deployment cancelled."
    exit 0
}

# Start deployment
$startTime = Get-Date

# 1. Create or Verify Resource Group
Write-Step "Checking resource group..."
$rgExists = az group exists --name $ResourceGroupName

if ($rgExists -eq "true") {
    Write-Info "Resource group already exists: $ResourceGroupName"
    $existingRg = az group show --name $ResourceGroupName | ConvertFrom-Json
    Write-Info "Location: $($existingRg.location)"
} else {
    Write-Info "Creating new resource group..."
    az group create `
        --name $ResourceGroupName `
        --location $Location `
        --output none
    Write-Success "Resource group created: $ResourceGroupName"
}

# 2. Create or Verify Storage Account
Write-Step "Checking storage account..."
$storageExists = az storage account check-name --name $StorageAccountName | ConvertFrom-Json

if ($storageExists.nameAvailable -eq $false -and $storageExists.reason -eq "AlreadyExists") {
    Write-Info "Storage account already exists: $StorageAccountName"
    # Verify it's in our resource group
    try {
        $existingStorage = az storage account show --name $StorageAccountName --resource-group $ResourceGroupName 2>$null | ConvertFrom-Json
        Write-Success "Using existing storage account in resource group"
    } catch {
        Write-Error "Storage account '$StorageAccountName' exists but not in resource group '$ResourceGroupName'"
        exit 1
    }
} else {
    Write-Info "Creating new storage account..."
    az storage account create `
        --name $StorageAccountName `
        --resource-group $ResourceGroupName `
        --location $Location `
        --sku Standard_LRS `
        --kind StorageV2 `
        --allow-blob-public-access false `
        --min-tls-version TLS1_2 `
        --output none
    Write-Success "Storage account created: $StorageAccountName"
}

# 3. Create Blob Containers
Write-Step "Creating blob containers..."

# Get storage account key for container creation
$storageKey = az storage account keys list `
    --resource-group $ResourceGroupName `
    --account-name $StorageAccountName `
    --query '[0].value' `
    --output tsv

az storage container create `
    --name datasets `
    --account-name $StorageAccountName `
    --account-key $storageKey `
    --output none

az storage container create `
    --name locks `
    --account-name $StorageAccountName `
    --account-key $storageKey `
    --output none

Write-Success "Containers created: datasets, locks"

# 4. Create Function App
Write-Step "Creating Function App..."

# Check if function app already exists
$funcExists = az functionapp show --name $FunctionAppName --resource-group $ResourceGroupName 2>$null

if ($funcExists) {
    Write-Info "Function app already exists: $FunctionAppName"
    Write-Info "Skipping creation, will update configuration..."
} else {
    Write-Info "Creating new function app with consumption plan..."
    
    # Create Function App with consumption plan (no separate plan needed)
    az functionapp create `
        --resource-group $ResourceGroupName `
        --name $FunctionAppName `
        --storage-account $StorageAccountName `
        --consumption-plan-location $Location `
        --runtime python `
        --runtime-version 3.11 `
        --functions-version 4 `
        --os-type Linux `
        --disable-app-insights false `
        --output none
    
    Write-Success "Function App created: $FunctionAppName"
}

# Enable managed identity if not already enabled
Write-Info "Ensuring managed identity is enabled..."
az functionapp identity assign `
    --resource-group $ResourceGroupName `
    --name $FunctionAppName `
    --output none 2>$null

Write-Success "Managed identity configured"

# 5. Create Key Vault and Store Secrets
Write-Step "Creating Azure Key Vault..."

# Check if Key Vault already exists
$kvExists = az keyvault show --name $KeyVaultName --resource-group $ResourceGroupName 2>$null

if ($kvExists) {
    Write-Info "Key Vault already exists: $KeyVaultName"
} else {
    Write-Info "Creating new Key Vault..."
    az keyvault create `
        --name $KeyVaultName `
        --resource-group $ResourceGroupName `
        --location $Location `
        --enable-rbac-authorization false `
        --output none
    Write-Success "Key Vault created: $KeyVaultName"
}

# Store MaxMind License Key if provided
if ($MaxMindLicenseKey) {
    Write-Info "Storing MaxMind license key in Key Vault..."
    az keyvault secret set `
        --vault-name $KeyVaultName `
        --name "MAXMIND-LICENSE-KEY" `
        --value $MaxMindLicenseKey `
        --output none
    Write-Success "MaxMind license key stored"
} else {
    Write-Info "MaxMind license key not provided, skipping Key Vault secret creation"
    Write-Info "You can add it later with: az keyvault secret set --vault-name $KeyVaultName --name MAXMIND-LICENSE-KEY --value '<your-key>'"
}

# Get Managed Identity Principal ID for Key Vault access
$principalId = az functionapp identity show `
    --resource-group $ResourceGroupName `
    --name $FunctionAppName `
    --query principalId `
    --output tsv

# Grant Function App access to Key Vault secrets
Write-Info "Granting Function App access to Key Vault..."
az keyvault set-policy `
    --name $KeyVaultName `
    --object-id $principalId `
    --secret-permissions get list `
    --output none

Write-Success "Function App granted Key Vault access (get, list secrets)"
Write-Info "Note: You can manually adjust Key Vault access policies in the portal if needed"

# 6. Create Azure Maps Account
Write-Step "Creating Azure Maps Account..."

# Check if Azure Maps account already exists
$mapsExists = az maps account show --name $AzureMapsAccountName --resource-group $ResourceGroupName 2>$null

if ($mapsExists) {
    Write-Info "Azure Maps account already exists: $AzureMapsAccountName"
} else {
    Write-Info "Creating new Azure Maps account (Gen2 - Standard S0)..."
    az maps account create `
        --name $AzureMapsAccountName `
        --resource-group $ResourceGroupName `
        --sku "G2" `
        --kind "Gen2" `
        --output none
    Write-Success "Azure Maps account created: $AzureMapsAccountName"
}

# Get Azure Maps subscription key
$mapsKey = az maps account keys list `
    --name $AzureMapsAccountName `
    --resource-group $ResourceGroupName `
    --query primaryKey `
    --output tsv

Write-Success "Azure Maps subscription key retrieved"

# 7. Create Static Web App
Write-Step "Creating Static Web App..."

# Check if SWA already exists
$swaExists = az staticwebapp show --name $StaticWebAppName --resource-group $ResourceGroupName 2>$null

if ($swaExists) {
    Write-Info "Static Web App already exists: $StaticWebAppName"
} else {
    Write-Info "Creating new Static Web App (Standard SKU for BYO Functions)..."
    az staticwebapp create `
        --name $StaticWebAppName `
        --resource-group $ResourceGroupName `
        --location $Location `
        --sku "Standard" `
        --output none
    Write-Success "Static Web App created: $StaticWebAppName"
}

# Get SWA deployment token
$swaToken = az staticwebapp secrets list `
    --name $StaticWebAppName `
    --resource-group $ResourceGroupName `
    --query properties.apiKey `
    --output tsv

Write-Success "Static Web App deployment token retrieved"

# Configure SWA app settings
Write-Info "Configuring Static Web App settings..."
$storageUrl = "https://$StorageAccountName.blob.core.windows.net"
az staticwebapp appsettings set `
    --name $StaticWebAppName `
    --resource-group $ResourceGroupName `
    --setting-names `
        STORAGE_ACCOUNT_URL=$storageUrl `
        STORAGE_CONTAINER_DATASETS=datasets `
        AZURE_MAPS_SUBSCRIPTION_KEY=$mapsKey `
    --output none

Write-Success "Static Web App settings configured"

# Function App-specific configuration (skip if -SkipFunctionApp is specified)
if (-not $SkipFunctionApp) {
    # 8. Configure App Settings
    Write-Step "Configuring application settings..."

    $storageUrl = "https://$StorageAccountName.blob.core.windows.net"

    az functionapp config appsettings set `
        --resource-group $ResourceGroupName `
        --name $FunctionAppName `
        --settings `
            LOG_ANALYTICS_WORKSPACE_ID=$WorkspaceId `
            STORAGE_ACCOUNT_URL=$storageUrl `
            STORAGE_CONTAINER_DATASETS=datasets `
            STORAGE_CONTAINER_LOCKS=locks `
            DEFAULT_REFRESH_INTERVAL_SECONDS=300 `
            DEFAULT_QUERY_TIME_WINDOW_HOURS=24 `
            INCREMENTAL_OVERLAP_MINUTES=10 `
            AzureWebJobsFeatureFlags=EnableWorkerIndexing `
            AZURE_MAPS_SUBSCRIPTION_KEY='' `
            AZURE_MAPS_CLIENT_ID='' `
            KEY_VAULT_NAME=$KeyVaultName `
        --output none

    Write-Info "Note: Azure Maps settings are empty by default. MaxMind license key stored in Key Vault."
    Write-Success "Application settings configured (Key Vault: $KeyVaultName)"

    # 9. Assign RBAC Roles
    Write-Step "Assigning RBAC roles..."

    # Storage Blob Data Contributor role
    $storageAccountId = az storage account show `
        --name $StorageAccountName `
        --resource-group $ResourceGroupName `
        --query id `
        --output tsv

    az role assignment create `
        --assignee $principalId `
        --role "Storage Blob Data Contributor" `
        --scope $storageAccountId `
        --output none

    Write-Success "Assigned Storage Blob Data Contributor role"

    # Log Analytics Reader role (if workspace is in same subscription)
    Write-Info "Note: You may need to manually assign 'Log Analytics Reader' role to the Function App's managed identity on your Log Analytics Workspace"
    Write-Info "Principal ID: $principalId"

    # 10. Deploy Function Code
    Write-Step "Deploying function code (with remote build for Python dependencies)..."

# Check if in api directory
$currentPath = Get-Location
if (Test-Path ".\function_app.py") {
    $apiPath = $currentPath
} elseif (Test-Path ".\api\function_app.py") {
    $apiPath = Join-Path $currentPath "api"
} else {
    Write-Error "Cannot find function_app.py. Please run from project root or api directory."
    exit 1
}

Push-Location $apiPath

# Deploy using func CLI if available, otherwise use zip deploy
try {
    if (Get-Command func -ErrorAction SilentlyContinue) {
        func azure functionapp publish $FunctionAppName --python
        Write-Success "Function deployed successfully using func CLI"
    } else {
        # Fallback to zip deploy
        Write-Info "Deploying using zip deploy method..."
        
        # Create temporary build directory
        $buildDir = Join-Path $env:TEMP "sentinel-maps-build"
        if (Test-Path $buildDir) {
            Remove-Item $buildDir -Recurse -Force
        }
        New-Item -ItemType Directory -Path $buildDir | Out-Null
        
        # Copy necessary files
        Copy-Item -Path "function_app.py" -Destination $buildDir
        Copy-Item -Path "host.json" -Destination $buildDir
        Copy-Item -Path "requirements.txt" -Destination $buildDir
        Copy-Item -Path "sources.yaml" -Destination $buildDir
        Copy-Item -Path "shared" -Destination $buildDir -Recurse
        
        # Create zip file
        $zipPath = Join-Path $env:TEMP "sentinel-maps-deploy.zip"
        if (Test-Path $zipPath) {
            Remove-Item $zipPath -Force
        }
        
        Compress-Archive -Path "$buildDir\*" -DestinationPath $zipPath
        
        # Deploy zip
        az functionapp deployment source config-zip `
            --resource-group $ResourceGroupName `
            --name $FunctionAppName `
            --src $zipPath `
            --build-remote true `
            --timeout 600 `
            --output none
        
        # Cleanup
        Remove-Item $buildDir -Recurse -Force
        Remove-Item $zipPath -Force
        
        Write-Success "Function deployed successfully using zip deploy"
    }
} catch {
    Write-Error "Function deployment failed: $_"
    Pop-Location
    exit 1
} finally {
    Pop-Location
}
} # End of SkipFunctionApp check

# Summary
$duration = (Get-Date) - $startTime
Write-Host "`n================================================" -ForegroundColor Green
Write-Host "Deployment Complete!" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Green
Write-Host "Duration:          $($duration.Minutes)m $($duration.Seconds)s"
Write-Host "Resource Group:    $ResourceGroupName"
if (-not $SkipFunctionApp) {
    Write-Host "Function App:      $FunctionAppName"
}
Write-Host "Storage Account:   $StorageAccountName"
Write-Host "Static Web App:    $StaticWebAppName"
Write-Host "Azure Maps:        $AzureMapsAccountName"
if (-not $SkipFunctionApp) {
    Write-Host "`nFunction Endpoints:"
    Write-Host "  Health:  https://$FunctionAppName.azurewebsites.net/api/health"
    Write-Host "  Refresh: https://$FunctionAppName.azurewebsites.net/api/refresh"
}
Write-Host "`n================================================" -ForegroundColor Green

if (-not $SkipFunctionApp) {
    Write-Host "`n⚠️  Important Next Steps:" -ForegroundColor Yellow
    Write-Host "1. Assign 'Log Analytics Reader' role to the Function App on your Log Analytics Workspace" -ForegroundColor Yellow
    Write-Host "   Principal ID: $principalId" -ForegroundColor White
    Write-Host ""
    Write-Host "   Option A - Via Function App Identity (Easiest):" -ForegroundColor Cyan
    Write-Host "   1. Go to Azure Portal → Function App '$FunctionAppName'" -ForegroundColor White
    Write-Host "   2. Click 'Identity' in the left menu" -ForegroundColor White
    Write-Host "   3. Go to 'Azure role assignments' tab" -ForegroundColor White
    Write-Host "   4. Click '+ Add role assignment'" -ForegroundColor White
    Write-Host "   5. Scope: Select your Log Analytics Workspace" -ForegroundColor White
    Write-Host "   6. Role: Select 'Log Analytics Reader'" -ForegroundColor White
    Write-Host "   7. Click 'Save'" -ForegroundColor White
    Write-Host ""
    Write-Host "   Option B - Azure CLI:" -ForegroundColor Cyan
    Write-Host "   az role assignment create --assignee $principalId --role 'Log Analytics Reader' --scope /subscriptions/<sub-id>/resourceGroups/<workspace-rg>/providers/Microsoft.OperationalInsights/workspaces/<workspace-name>" -ForegroundColor Gray
    Write-Host ""
    Write-Host "2. Test the deployment:" -ForegroundColor Yellow
    Write-Host "   Invoke-RestMethod https://$FunctionAppName.azurewebsites.net/api/health" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "3. Trigger a data refresh:" -ForegroundColor Yellow
    Write-Host "   Invoke-RestMethod https://$FunctionAppName.azurewebsites.net/api/refresh" -ForegroundColor Cyan
}
