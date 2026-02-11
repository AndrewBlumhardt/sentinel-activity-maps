#Requires -Version 7.0
<#
.SYNOPSIS
    Cleanup script for Sentinel Activity Maps Azure resources

.DESCRIPTION
    This script removes all Azure resources created for Sentinel Activity Maps.
    WARNING: This will permanently delete all resources in the specified resource group.

.PARAMETER ResourceGroupName
    Name of the resource group to delete (default: rg-sentinel-activity-maps)

.PARAMETER Force
    Skip confirmation prompt

.EXAMPLE
    .\cleanup.ps1

.EXAMPLE
    .\cleanup.ps1 -ResourceGroupName "rg-sentinel-activity-maps" -Force
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$false)]
    [string]$ResourceGroupName = "rg-sentinel-activity-maps",
    
    [Parameter(Mandatory=$false)]
    [switch]$Force
)

$ErrorActionPreference = "Stop"

# Color output functions
function Write-Warning {
    param([string]$Message)
    Write-Host "⚠️  $Message" -ForegroundColor Yellow
}

function Write-Info {
    param([string]$Message)
    Write-Host "ℹ  $Message" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "✓ $Message" -ForegroundColor Green
}

function Write-Error {
    param([string]$Message)
    Write-Host "✗ $Message" -ForegroundColor Red
}

# Check Azure CLI
try {
    az version --output json 2>$null | Out-Null
} catch {
    Write-Error "Azure CLI not found. Please install: https://aka.ms/install-azure-cli"
    exit 1
}

# Check if logged in
$account = az account show 2>$null | ConvertFrom-Json
if (-not $account) {
    Write-Error "Not logged in to Azure. Run 'az login' first."
    exit 1
}

Write-Info "Logged in as: $($account.user.name)"
Write-Info "Subscription: $($account.name)"

# Check if resource group exists
Write-Host "`nChecking for resource group: $ResourceGroupName..."
$rgExists = az group exists --name $ResourceGroupName

if ($rgExists -eq "false") {
    Write-Warning "Resource group '$ResourceGroupName' does not exist."
    exit 0
}

# List resources in the group
Write-Host "`nResources to be deleted:"
Write-Host "========================"
$resources = az resource list --resource-group $ResourceGroupName | ConvertFrom-Json

if ($resources.Count -eq 0) {
    Write-Info "No resources found in resource group."
} else {
    foreach ($resource in $resources) {
        Write-Host "  - $($resource.name) ($($resource.type))" -ForegroundColor Yellow
    }
}

Write-Host "========================"
Write-Host "Resource Group: $ResourceGroupName" -ForegroundColor Red
Write-Host "Total Resources: $($resources.Count)" -ForegroundColor Red
Write-Host "========================`n"

# Confirmation
if (-not $Force) {
    Write-Warning "This will permanently delete ALL resources in the resource group."
    Write-Warning "This action cannot be undone!"
    $confirmation = Read-Host "`nType 'DELETE' to confirm"
    
    if ($confirmation -ne "DELETE") {
        Write-Info "Cleanup cancelled."
        exit 0
    }
}

# Start deletion
Write-Host "`nDeleting resource group..." -ForegroundColor Cyan
$startTime = Get-Date

try {
    az group delete `
        --name $ResourceGroupName `
        --yes `
        --no-wait
    
    Write-Success "Deletion initiated successfully."
    Write-Info "Resources are being deleted in the background."
    Write-Info "This may take several minutes to complete."
    
    $duration = (Get-Date) - $startTime
    
    Write-Host "`n================================================" -ForegroundColor Green
    Write-Host "Cleanup Complete!" -ForegroundColor Green
    Write-Host "================================================" -ForegroundColor Green
    Write-Host "Resource Group: $ResourceGroupName"
    Write-Host "Status:         Deletion in progress"
    Write-Host "Time taken:     $($duration.Seconds)s"
    Write-Host "================================================`n" -ForegroundColor Green
    
    Write-Info "To check deletion status, run:"
    Write-Host "  az group show --name $ResourceGroupName" -ForegroundColor Cyan
    
} catch {
    Write-Error "Failed to delete resource group: $_"
    exit 1
}
