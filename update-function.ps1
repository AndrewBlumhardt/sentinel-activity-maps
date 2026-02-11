#Requires -Version 7.0
<#
.SYNOPSIS
    Quick code update script for Sentinel Activity Maps Azure Function

.DESCRIPTION
    Deploys updated function code to an existing Azure Function App without
    recreating resources. Use this for quick code updates during development.

.PARAMETER FunctionAppName
    Name of the existing Function App to update

.PARAMETER ResourceGroupName
    Name of the resource group containing the Function App

.PARAMETER Cloud
    Azure cloud environment (AzureCloud, AzureUSGovernment)
    Default: AzureCloud

.EXAMPLE
    .\update-function.ps1 -FunctionAppName "sentinel-activity-maps-func-12345"

.EXAMPLE
    .\update-function.ps1 -FunctionAppName "my-func" -ResourceGroupName "my-rg" -Cloud AzureUSGovernment

.NOTES
    This script only updates code - it does not modify app settings or infrastructure.
    For full deployment, use deploy.ps1
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [string]$FunctionAppName,
    
    [Parameter(Mandatory=$false)]
    [string]$ResourceGroupName = "rg-sentinel-activity-maps",
    
    [Parameter(Mandatory=$false)]
    [ValidateSet("AzureCloud", "AzureUSGovernment")]
    [string]$Cloud = "AzureCloud"
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

# Login check
Write-Step "Checking Azure login..."
$account = az account show 2>$null | ConvertFrom-Json
if (-not $account) {
    Write-Info "Not logged in. Starting login to $Cloud..."
    if ($Cloud -eq "AzureUSGovernment") {
        az cloud set --name AzureUSGovernment
    }
    az login
    $account = az account show | ConvertFrom-Json
} else {
    # Verify cloud
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

# Verify function app exists
Write-Step "Verifying Function App exists..."
$funcApp = az functionapp show --name $FunctionAppName --resource-group $ResourceGroupName 2>$null | ConvertFrom-Json

if (-not $funcApp) {
    Write-Error "Function App '$FunctionAppName' not found in resource group '$ResourceGroupName'"
    Write-Info "Available Function Apps in resource group:"
    az functionapp list --resource-group $ResourceGroupName --query "[].name" -o tsv
    exit 1
}

Write-Success "Found Function App: $FunctionAppName"
Write-Info "Location: $($funcApp.location)"
Write-Info "Runtime: $($funcApp.kind)"

# Start deployment
$startTime = Get-Date

Write-Step "Deploying function code..."

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

try {
    # Try using func CLI first
    if (Get-Command func -ErrorAction SilentlyContinue) {
        Write-Info "Using Azure Functions Core Tools..."
        func azure functionapp publish $FunctionAppName --python
        Write-Success "Function deployed successfully using func CLI"
    } else {
        # Fallback to zip deploy
        Write-Info "Using zip deploy method..."
        
        # Create temporary build directory
        $buildDir = Join-Path $env:TEMP "sentinel-maps-build"
        if (Test-Path $buildDir) {
            Remove-Item $buildDir -Recurse -Force
        }
        New-Item -ItemType Directory -Path $buildDir | Out-Null
        
        # Copy necessary files
        Write-Info "Packaging function code..."
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
        Write-Info "Uploading to Azure..."
        az functionapp deployment source config-zip `
            --resource-group $ResourceGroupName `
            --name $FunctionAppName `
            --src $zipPath `
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

# Restart function app to ensure changes take effect
Write-Step "Restarting Function App..."
az functionapp restart --name $FunctionAppName --resource-group $ResourceGroupName --output none
Write-Success "Function App restarted"

# Summary
$duration = (Get-Date) - $startTime
Write-Host "`n================================================" -ForegroundColor Green
Write-Host "Code Update Complete!" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Green
Write-Host "Duration:       $($duration.Minutes)m $($duration.Seconds)s"
Write-Host "Function App:   $FunctionAppName"
Write-Host "`nEndpoints:"
Write-Host "  Health:  https://$FunctionAppName.azurewebsites.net/api/health"
Write-Host "  Refresh: https://$FunctionAppName.azurewebsites.net/api/refresh"
Write-Host "`n================================================" -ForegroundColor Green

Write-Host "`nℹ️  Testing the deployment:" -ForegroundColor Cyan
Write-Host "  Invoke-WebRequest https://$FunctionAppName.azurewebsites.net/api/health" -ForegroundColor Gray
Write-Host ""
Write-Host "Note: It may take 30-60 seconds for the function to be fully ready." -ForegroundColor Yellow

Write-Host "`n✓ Code update completed successfully!" -ForegroundColor Green
