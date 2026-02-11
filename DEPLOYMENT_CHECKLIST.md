# Deployment Checklist

Quick reference for deploying Sentinel Activity Maps Function backend.

## 📋 Pre-Deployment Checklist

- [ ] Azure CLI installed (`az --version`)
- [ ] Logged into Azure (`az login`)
- [ ] Have Log Analytics Workspace ID (GUID format)
- [ ] Have **Owner or Contributor** permissions on subscription or target resource group
- [ ] Confirmed Azure cloud (Commercial, GCC, or GCC-High)

## 🚀 Deployment Options

### Option 1: Automated Script (Recommended)

**Time: ~5 minutes**

**PowerShell (Windows):**
```powershell
.\deploy.ps1 -WorkspaceId "12345678-1234-1234-1234-123456789012"

# For Azure Government (GCC/GCC-High)
.\deploy.ps1 -WorkspaceId "12345678-1234-1234-1234-123456789012" -Cloud AzureUSGovernment
```

**Bash (Linux/macOS/WSL):**
```bash
./deploy.sh --workspace-id "12345678-1234-1234-1234-123456789012"

# For Azure Government (GCC/GCC-High)
./deploy.sh --workspace-id "12345678-1234-1234-1234-123456789012" --cloud AzureUSGovernment
```

**Script Parameters:**
- `--workspace-id` (required) - Your Log Analytics Workspace ID
- `--resource-group` (optional) - Default: `rg-sentinel-activity-maps`
- `--location` (optional) - Default: `eastus`
- `--storage-account` (optional) - Must be 3-24 chars, lowercase alphanumeric
  - Default: `sentinelactmapsXXXXX` (auto-generated)
- `--function-app` (optional) - Default: `sentinel-activity-maps-func-XXXXX`

**Notes:**
- Storage account names must be globally unique
- Scripts detect and use existing resources (idempotent)
- Resources can be pre-created manually before running scripts

### Option 2: Manual Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for step-by-step Azure CLI commands.

### Option 3: GitHub Actions CI/CD

See [.github/workflows/deploy-function.yml](.github/workflows/deploy-function.yml)

## ✅ Post-Deployment Steps

### 1. Assign Log Analytics Reader Role

**Critical:** The deployment script cannot automatically assign this role if the workspace is in a different resource group or subscription.

**Get your Function's Principal ID:**
```bash
az functionapp identity show \
    --name YOUR-FUNCTION-APP \
    --resource-group rg-sentinel-activity-maps \
    --query principalId -o tsv
```

**Assign the role:**

**Via Azure Portal (Recommended):**
1. Navigate to your **Function App** in Azure Portal
2. Click **Identity** in the left menu
3. Go to the **Azure role assignments** tab
4. Click **+ Add role assignment**
5. **Scope:** Select your Log Analytics Workspace
6. **Role:** Select **Log Analytics Reader**
7. Click **Save**

**Via Azure CLI:**
```bash
az role assignment create \
    --assignee <PRINCIPAL-ID> \
    --role "Log Analytics Reader" \
    --scope "/subscriptions/<SUB-ID>/resourceGroups/<WORKSPACE-RG>/providers/Microsoft.OperationalInsights/workspaces/<WORKSPACE-NAME>"
```

**Via Azure Portal:**
1. Navigate to your Log Analytics Workspace
2. Go to **Access control (IAM)**
3. Click **Add role assignment**
4. Select **Log Analytics Reader** role
5. Click **Next**
6. Select **Managed Identity**
7. Choose **Function App** and select your function
8. Click **Review + assign**

### 2. Verify Deployment

**Test health endpoint:**
```bash
curl https://YOUR-FUNCTION-APP.azurewebsites.net/api/health
```

**Expected response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-02-07T12:34:56Z",
  "sources_configured": 2
}
```

### 3. Trigger First Refresh

```bash
curl -X POST https://YOUR-FUNCTION-APP.azurewebsites.net/api/refresh
```

**Expected response:**
```json
{
  "message": "Refreshed 2/2 sources",
  "refreshed_count": 2,
  "total_sources": 2,
  "results": [...]
}
```

### 4. Verify Data Output

**List blobs in datasets container:**
```bash
az storage blob list \
    --container-name datasets \
    --account-name YOUR-STORAGE-ACCOUNT \
    --auth-mode login \
    --output table
```

**You should see:**
- `signin-failures.tsv`
- `threat-intel-indicators.tsv`

### 5. Monitor Logs

**Stream live logs:**
```bash
az functionapp log tail \
    --resource-group sentinel-activity-maps-rg \
    --name YOUR-FUNCTION-APP
```

**Or view in Azure Portal:**
- Navigate to Function App → Monitoring → Log stream

## 🔍 Verification Checklist

- [ ] Health endpoint returns `200 OK`
- [ ] Log Analytics Reader role assigned
- [ ] Refresh endpoint returns `200` or `204`
- [ ] TSV files created in `datasets` container
- [ ] Metadata files created in `locks` container
- [ ] No errors in function logs

## 🛠️ Common Issues

### Issue: 401 Unauthorized from Log Analytics

**Fix:** Assign Log Analytics Reader role (see step 1 above)

### Issue: Storage access denied

**Fix:** Verify Storage Blob Data Contributor role:
```bash
az role assignment list \
    --assignee <PRINCIPAL-ID> \
    --scope /subscriptions/<SUB>/resourceGroups/<RG>/providers/Microsoft.Storage/storageAccounts/<ACCOUNT>
```

### Issue: Function returns 500 Internal Server Error

**Fix:** Check function logs for details:
```bash
az functionapp log tail --name YOUR-FUNCTION-APP --resource-group YOUR-RG
```

### Issue: No data in TSV files

**Causes:**
- No matching data in Log Analytics for time window
- Query syntax error in `sources.yaml`
- Time window too narrow

**Fix:**
1. Test query in Log Analytics to verify data exists
2. Increase `query_time_window_hours` in `api/sources.yaml`
3. Check logs for KQL errors

## 🧹 Cleanup

To remove all resources:

**PowerShell:**
```powershell
.\cleanup.ps1 -ResourceGroupName "sentinel-activity-maps-rg"
```

**Bash:**
```bash
./cleanup.sh --resource-group "sentinel-activity-maps-rg"
```

**Manual:**
```bash
az group delete --name sentinel-activity-maps-rg --yes
```

## 📚 Additional Resources

- **[Full Deployment Guide](DEPLOYMENT.md)** - Detailed manual steps
- **[Local Development](LOCAL_DEVELOPMENT.md)** - Run locally without Azure
- **[Quick Start](QUICKSTART.md)** - 5-minute local setup
- **[Architecture](docs/architecture.md)** - System design details

## 💡 Tips

- Use unique names for storage account and function app to avoid conflicts
- Deploy to same region as Log Analytics workspace for better performance
- Enable Application Insights for detailed monitoring (added automatically)
- Use consumption plan (Y1) to minimize costs for infrequent refreshes
- Consider Premium plan if you need faster execution or VNet integration

## 🔐 Security Best Practices

✅ **Enabled by default:**
- Managed Identity (no connection strings)
- HTTPS only
- TLS 1.2 minimum
- No public blob access
- RBAC for storage access

🔒 **Consider adding:**
- VNet integration for private connectivity
- Private endpoints for storage
- Azure Key Vault for additional secrets (if needed)
- Azure Monitor alerts for failures
