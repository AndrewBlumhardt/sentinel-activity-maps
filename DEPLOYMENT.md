# Deployment Guide

This guide provides both automated and manual deployment instructions for the Sentinel Activity Maps Function backend.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Automated Deployment (Recommended)](#automated-deployment-recommended)
- [Manual Deployment](#manual-deployment)
- [Post-Deployment Configuration](#post-deployment-configuration)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Tools
- **Azure CLI** - [Install Guide](https://aka.ms/install-azure-cli)
- **Azure Subscription** with Owner or Contributor permissions on subscription or target resource group
- **Log Analytics Workspace** - Already configured with Sentinel (or test data)

### Azure Permissions
**Required:** Owner or Contributor role on:
- The target subscription (recommended), OR
- The target resource group (if pre-created)

**To check your permissions:**
```bash
# Check subscription-level access
az role assignment list --assignee $(az account show --query user.name -o tsv) --include-inherited
```

### Required Information
Before deploying, gather the following:
1. **Log Analytics Workspace ID** (GUID format)
   - Find in: Azure Portal → Your Log Analytics Workspace → Properties → Workspace ID
2. **Azure Subscription ID** (optional, uses current subscription if not specified)

---

## Automated Deployment (Recommended)

The automated scripts will create all required resources and deploy your function in ~5 minutes.

**Important Notes:**
- Storage account names must be globally unique, 3-24 characters, lowercase alphanumeric only
- Scripts will detect and use existing resources if they already exist
- Resource group, storage account, and function app can be pre-created

### Option 1: PowerShell (Windows)

```powershell
# Navigate to project root
cd c:\repos\sentinel-activity-maps

# Run deployment script
.\deploy.ps1 -WorkspaceId "YOUR-WORKSPACE-ID-HERE"
```

**Custom configuration:**
```powershell
.\deploy.ps1 `
    -WorkspaceId "12345678-1234-1234-1234-123456789012" `
    -ResourceGroupName "rg-sentinel-activity-maps" `
    -Location "westus2" `
    -StorageAccountName "sentinelactmaps001" `
    -FunctionAppName "sentinel-activity-maps-func"
```

**For Azure Government (GCC/GCC-High):**
```powershell
.\deploy.ps1 `
    -WorkspaceId "YOUR-WORKSPACE-ID" `
    -Cloud AzureUSGovernment
```

**Note:** The script will prompt you to login if not already authenticated and verify you have sufficient permissions.

### Option 2: Bash (Linux/macOS/WSL)

```bash
# Make script executable
chmod +x deploy.sh

# Run deployment script
./deploy.sh --workspace-id "YOUR-WORKSPACE-ID-HERE"
```

**Custom configuration:**
```bash
./deploy.sh \
    --workspace-id "12345678-1234-1234-1234-123456789012" \
    --resource-group "rg-sentinel-activity-maps" \
    --location "westus2" \
    --storage-account "sentinelactmaps001" \
    --function-app "sentinel-activity-maps-func"
```

**For Azure Government (GCC/GCC-High):**
```bash
./deploy.sh \
    --workspace-id "YOUR-WORKSPACE-ID" \
    --cloud AzureUSGovernment
```

### What the Script Creates

1. **Resource Group** - Container for all resources (or uses existing)
2. **Storage Account** (Standard_LRS) - (or uses existing)
   - `datasets` container - TSV output files
   - `locks` container - Locking and metadata
3. **Function App** (Python 3.11, Linux, Consumption Plan)
   - System-assigned managed identity
   - Configured app settings
4. **RBAC Assignments**
   - Storage Blob Data Contributor (on storage account)

**Note:** The scripts are idempotent - they will detect existing resources and skip creation if already present.

---

## Manual Deployment

If you prefer manual control or the automated scripts don't work in your environment:

### Step 1: Create Resource Group

```bash
az group create \
    --name sentinel-activity-maps-rg \
    --location eastus
```

### Step 2: Create Storage Account

```bash
az storage account create \
    --name sentinelmaps$(date +%s) \
    --resource-group sentinel-activity-maps-rg \
    --location eastus \
    --sku Standard_LRS \
    --kind StorageV2 \
    --allow-blob-public-access false \
    --min-tls-version TLS1_2
```

**Get the storage account name for next steps:**
```bash
STORAGE_ACCOUNT_NAME="your-storage-account-name"
```

### Step 3: Create Blob Containers

```bash
# Get storage key
STORAGE_KEY=$(az storage account keys list \
    --resource-group sentinel-activity-maps-rg \
    --account-name $STORAGE_ACCOUNT_NAME \
    --query '[0].value' \
    --output tsv)

# Create containers
az storage container create \
    --name datasets \
    --account-name $STORAGE_ACCOUNT_NAME \
    --account-key $STORAGE_KEY

az storage container create \
    --name locks \
    --account-name $STORAGE_ACCOUNT_NAME \
    --account-key $STORAGE_KEY
```

### Step 4: Create Function App

```bash
# Create App Service Plan
az functionapp plan create \
    --resource-group sentinel-activity-maps-rg \
    --name sentinel-maps-plan \
    --location eastus \
    --number-of-workers 1 \
    --sku Y1 \
    --is-linux

# Create Function App
az functionapp create \
    --resource-group sentinel-activity-maps-rg \
    --name sentinel-maps-func-$(date +%s) \
    --storage-account $STORAGE_ACCOUNT_NAME \
    --plan sentinel-maps-plan \
    --runtime python \
    --runtime-version 3.11 \
    --functions-version 4 \
    --os-type Linux \
    --assign-identity '[system]'
```

**Save the function app name:**
```bash
FUNCTION_APP_NAME="your-function-app-name"
```

### Step 5: Configure Application Settings

```bash
az functionapp config appsettings set \
    --resource-group sentinel-activity-maps-rg \
    --name $FUNCTION_APP_NAME \
    --settings \
        LOG_ANALYTICS_WORKSPACE_ID="YOUR-WORKSPACE-ID" \
        STORAGE_ACCOUNT_URL="https://$STORAGE_ACCOUNT_NAME.blob.core.windows.net" \
        STORAGE_CONTAINER_DATASETS=datasets \
        STORAGE_CONTAINER_LOCKS=locks \
        DEFAULT_REFRESH_INTERVAL_SECONDS=300 \
        DEFAULT_QUERY_TIME_WINDOW_HOURS=24 \
        INCREMENTAL_OVERLAP_MINUTES=10
```

### Step 6: Assign Managed Identity RBAC Roles

```bash
# Get principal ID
PRINCIPAL_ID=$(az functionapp identity show \
    --resource-group sentinel-activity-maps-rg \
    --name $FUNCTION_APP_NAME \
    --query principalId \
    --output tsv)

# Get storage account ID
STORAGE_ACCOUNT_ID=$(az storage account show \
    --name $STORAGE_ACCOUNT_NAME \
    --resource-group sentinel-activity-maps-rg \
    --query id \
    --output tsv)

# Assign Storage Blob Data Contributor
az role assignment create \
    --assignee $PRINCIPAL_ID \
    --role "Storage Blob Data Contributor" \
    --scope $STORAGE_ACCOUNT_ID
```

### Step 7: Assign Log Analytics Reader Role

**Important:** You need to manually assign the Log Analytics Reader role to the function's managed identity.
**Option A - Azure Portal (Recommended):**

1. Navigate to your **Log Analytics Workspace** in Azure Portal
2. Click **Access control (IAM)** in the left menu
3. Click **+ Add** → **Add role assignment**
4. Select **Log Analytics Reader** role → Click **Next**
5. In the "Members" tab, select **Managed Identity**
6. Click **+ Select members**
7. In the dropdown, choose **Function App**
8. Select your function app (e.g., `sentinel-activity-maps-func-12345`)
9. Click **Select** button
10. Click **Review + assign**

**Option B - Azure CLI:**
```bash
# Replace <subscription-id>, <workspace-rg>, and <workspace-name> with your values
az role assignment create \
    --assignee $PRINCIPAL_ID \
    --role "Log Analytics Reader" \
    --scope "/subscriptions/<subscription-id>/resourceGroups/<workspace-rg>/providers/Microsoft.OperationalInsights/workspaces/<workspace-name>"
```

**Option B - Azure CLI:**

```bash
# Replace <subscription-id>, <workspace-rg>, and <workspace-name> with your values
az role assignment create \
    --assignee $PRINCIPAL_ID \
    --role "Log Analytics Reader" \
    --scope "/subscriptions/<subscription-id>/resourceGroups/<workspace-rg>/providers/Microsoft.OperationalInsights/workspaces/<workspace-name>"
```

### Step 8: Deploy Function Code

**Option A: Using Azure Functions Core Tools**
```bash
cd api
func azure functionapp publish $FUNCTION_APP_NAME --python
```

**Option B: Using ZIP deployment**
```bash
cd api

# Create zip file (Linux/macOS)
zip -r deploy.zip function_app.py host.json requirements.txt sources.yaml shared/

# Create zip file (Windows PowerShell)
Compress-Archive -Path function_app.py,host.json,requirements.txt,sources.yaml,shared -DestinationPath deploy.zip

# Deploy
az functionapp deployment source config-zip \
    --resource-group sentinel-activity-maps-rg \
    --name $FUNCTION_APP_NAME \
    --src deploy.zip
```

---

## Post-Deployment Configuration

### 1. Verify Deployment

Test the health endpoint:
```bash
curl https://$FUNCTION_APP_NAME.azurewebsites.net/api/health
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2026-02-07T12:34:56Z",
  "sources_configured": 2
}
```

### 2. Trigger First Refresh

```bash
curl -X POST https://$FUNCTION_APP_NAME.azurewebsites.net/api/refresh
```

### 3. Verify Data Output

Check that TSV files were created in the `datasets` container:

```bash
az storage blob list \
    --container-name datasets \
    --account-name $STORAGE_ACCOUNT_NAME \
    --output table
```

You should see:
- `signin-failures.tsv`
- `threat-intel-indicators.tsv`

### 4. Monitor Function Logs

```bash
# Stream live logs
az functionapp log tail \
    --resource-group sentinel-activity-maps-rg \
    --name $FUNCTION_APP_NAME

# Or view in Azure Portal
# Navigate to: Function App → Monitoring → Log stream
```

---

## Troubleshooting

### Issue: 404 Not Found after deployment

**Cause:** Function app is still in "cold start" phase (not fully initialized)

**Fix:**
Wait 30-60 seconds after deployment for the function app to fully start, then try again:
```bash
# Wait a minute, then test
curl https://<function-app-name>.azurewebsites.net/api/health

# Or if still getting 404, restart the function app
az functionapp restart --resource-group sentinel-activity-maps-rg --name <function-app-name>

# Then wait another 30-60 seconds before testing
```

**Note:** Consumption plan functions can take 30-60 seconds to become available after deployment or restart. This is normal behavior.

### Issue: "Unauthorized" when querying Log Analytics

**Cause:** Managed identity doesn't have Log Analytics Reader role

**Fix:**
```bash
# Get principal ID
PRINCIPAL_ID=$(az functionapp identity show \
    --resource-group sentinel-activity-maps-rg \
    --name $FUNCTION_APP_NAME \
    --query principalId \
    --output tsv)

# Assign role (update the scope with your workspace details)
az role assignment create \
    --assignee $PRINCIPAL_ID \
    --role "Log Analytics Reader" \
    --scope "/subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.OperationalInsights/workspaces/<workspace-name>"
```

### Issue: "BlobNotFound" or storage errors

**Cause:** Managed identity doesn't have storage permissions or containers don't exist

**Fix:**
```bash
# Verify containers exist
az storage container list \
    --account-name $STORAGE_ACCOUNT_NAME \
    --output table

# Verify RBAC assignment
az role assignment list \
    --assignee $PRINCIPAL_ID \
    --scope $STORAGE_ACCOUNT_ID \
    --output table
```

### Issue: Function deployment fails

**Cause:** Various reasons (missing files, wrong path, etc.)

**Fix:**
```bash
# Check deployment status
az functionapp deployment list-publishing-profiles \
    --resource-group sentinel-activity-maps-rg \
    --name $FUNCTION_APP_NAME

# Redeploy
cd api
func azure functionapp publish $FUNCTION_APP_NAME --python --build remote
```

### Issue: "No data" in TSV files

**Cause:** No matching data in Log Analytics for the configured queries

**Fix:**
1. Verify your Log Analytics workspace has data:
   - Check `SigninLogs` table in Azure Portal
   - Check `ThreatIntelligenceIndicator` table
2. Adjust time windows in `sources.yaml`:
   ```yaml
   query_time_window_hours: 168  # Increase to 7 days
   ```
3. Test query directly in Log Analytics to verify data exists

### Issue: Function times out

**Cause:** Large dataset or slow Log Analytics query

**Fix:**
1. Reduce time window in `sources.yaml`
2. Enable incremental queries (already enabled by default)
3. Consider upgrading to Premium plan for longer timeout

---

## Cleanup

To remove all deployed resources:

**PowerShell:**
```powershell
.\cleanup.ps1 -ResourceGroupName "sentinel-activity-maps-rg"
```

**Bash:**
```bash
./cleanup.sh --resource-group "sentinel-activity-maps-rg"
```

**Or manually:**
```bash
az group delete --name sentinel-activity-maps-rg --yes --no-wait
```

---

## Next Steps

1. **Configure CI/CD** - See `.github/workflows/deploy-function.yml` for automated deployments
2. **Add Custom Queries** - Edit `api/sources.yaml` to add more data sources
3. **Monitor Performance** - Set up Application Insights for detailed metrics
4. **Schedule Refreshes** - Create a Logic App or scheduled job to trigger `/api/refresh`
5. **Deploy Frontend** - Deploy the Static Web App to visualize the data

---

## Additional Resources

- [Azure Functions Python Developer Guide](https://learn.microsoft.com/azure/azure-functions/functions-reference-python)
- [Azure Managed Identity Overview](https://learn.microsoft.com/azure/active-directory/managed-identities-azure-resources/overview)
- [Kusto Query Language (KQL) Reference](https://learn.microsoft.com/azure/data-explorer/kusto/query/)
- [Azure Storage Blob Documentation](https://learn.microsoft.com/azure/storage/blobs/)
