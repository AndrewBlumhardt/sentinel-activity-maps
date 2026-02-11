# Update Summary - Code Update Scripts and Documentation

This document summarizes the latest updates to the Sentinel Activity Maps project.

## 🎯 What Was Added

### New Scripts

#### 1. update-function.ps1 (PowerShell)
**Purpose:** Update only the function code without modifying infrastructure or app settings.

**Features:**
- ✅ Fast execution (~1-2 minutes vs ~5 minutes for full deployment)
- ✅ Only deploys code from `api/` directory
- ✅ Preserves all app settings and RBAC configurations
- ✅ Automatic function app restart after deployment
- ✅ Warmup reminder (30-60 second cold start notice)
- ✅ Cloud support (AzureCloud, AzureUSGovernment)
- ✅ Verifies function app exists before deploying

**Usage:**
```powershell
.\update-function.ps1 -FunctionAppName "sentinel-activity-maps-func-12345"

# Azure Government
.\update-function.ps1 -FunctionAppName "your-func" -Cloud AzureUSGovernment
```

**Parameters:**
- `-FunctionAppName` (required): Name of the function app to update
- `-Cloud` (optional): Azure cloud environment (default: AzureCloud)
- `-Help`: Show help documentation

#### 2. update-function.sh (Bash)
**Purpose:** Cross-platform equivalent of update-function.ps1 for Linux/macOS/WSL.

**Features:** Same as PowerShell version

**Usage:**
```bash
./update-function.sh --function-app "sentinel-activity-maps-func-12345"

# Azure Government
./update-function.sh --function-app "your-func" --cloud AzureUSGovernment
```

**Parameters:**
- `--function-app` (required): Name of the function app to update
- `--cloud` (optional): Azure cloud environment (default: AzureCloud)
- `--help`: Show help documentation

---

## 📝 Documentation Updates

### 1. README.md
**Added:** New section "🔄 Update Function Code" after the Quick Deploy section

**Content:**
- Quick reference for using update scripts
- Cloud support examples
- Cold start warning (30-60 seconds after deployment)
- Link to GitHub Actions workflow for CI/CD

**Purpose:** Give users immediate visibility into code update options after initial deployment

### 2. DEPLOYMENT.md
**Added:** New troubleshooting entry for 404 errors after deployment

**Content:**
- Explanation of cold start behavior (30-60 seconds)
- Commands to restart function app if needed
- Note that this is normal for Consumption plan functions

**Purpose:** Help users understand why they might see 404 errors immediately after deployment and how to resolve them

### 3. DEPLOYMENT_SCRIPTS.md
**Updated:** Added entries for update-function scripts

**Content:**
- Script descriptions and features
- Usage examples for code updates
- Azure Government cloud examples
- Cold start warnings

**Purpose:** Provide comprehensive reference for all available deployment and management scripts

### 4. api/sources.yaml
**Updated:** threat_intel_indicators query to use correct table and schema

**Changes:**
- Table: `ThreatIntelligenceIndicator` → `ThreatIntelIndicators`
- Columns updated to match new schema:
  - `ObservableValue` (primary identifier)
  - `SourceSystem` (data source)
  - `Type` (from indicator_types)
  - `Label` (from labels)
  - `Confidence` (threat confidence score)
  - `Description` (indicator description)
  - `Created` (timestamp)
  - `IsActive` (active status)
- Added `arg_max` for deduplication by ObservableValue
- Added filter for "network" observable types

**Purpose:** Fix incorrect table name and align with current Microsoft Sentinel threat intelligence schema

---

## 🔀 When to Use Which Script

### Use `deploy.ps1` / `deploy.sh` when:
- ✅ First-time deployment
- ✅ Need to create or update infrastructure (storage, function app, app service plan)
- ✅ Need to configure or update app settings
- ✅ Need to assign or update RBAC roles
- ✅ Want idempotent deployment (safe to run multiple times)

**Duration:** ~5 minutes

### Use `update-function.ps1` / `update-function.sh` when:
- ✅ Only changed Python code in `api/` directory
- ✅ Want faster deployments during development
- ✅ Infrastructure and app settings are already configured
- ✅ Iterating on code changes

**Duration:** ~1-2 minutes (+ 30-60 second cold start)

### Use `cleanup.ps1` / `cleanup.sh` when:
- ⚠️ Need to delete all resources (testing, cost savings)
- ⚠️ Starting fresh with new deployment

**Duration:** ~2-5 minutes

---

## 🌐 Azure Government Support

All scripts now support Azure Government cloud environments (GCC, GCC-High):

**Default:** AzureCloud (Commercial Azure)
**Option:** AzureUSGovernment (Azure Government)

**Switching clouds:**
```powershell
# PowerShell
-Cloud AzureUSGovernment

# Bash
--cloud AzureUSGovernment
```

**Applies to:**
- deploy.ps1 / deploy.sh
- update-function.ps1 / update-function.sh
- cleanup.ps1 / cleanup.sh

---

## ⚠️ Important Notes

### Cold Start Behavior
After deploying code with update scripts (or deploy scripts), Azure Functions on Consumption plans take **30-60 seconds** to fully start. This is called a "cold start."

**Symptoms:**
- 404 errors on `/api/health` or `/api/refresh` immediately after deployment
- "Function not found" messages

**Solution:**
- Wait 60 seconds and try again
- Or manually restart: `az functionapp restart --resource-group <rg> --name <func-name>`

### App Settings Preservation
The update scripts **DO NOT** modify:
- App settings (LOG_ANALYTICS_WORKSPACE_ID, storage URLs, etc.)
- Managed identity configuration
- RBAC role assignments
- Function app configuration (runtime, OS, plan)

If you need to change any of these, use the full deployment scripts instead.

### Code Deployment Method
Update scripts use **zip deployment** (same as deploy scripts):
1. Packages entire `api/` directory into a .zip file
2. Uploads to Function App using Azure CLI
3. Azure Functions runtime unpacks and deploys code
4. Function app restarts automatically

**Advantages:**
- No need for Azure Functions Core Tools (`func` CLI)
- Works on any machine with Azure CLI
- Reliable and supported deployment method

---

## 🚀 CI/CD Integration

### Option 1: GitHub Actions (Automated)
Use the provided workflow at `.github/workflows/deploy-function.yml`:

**Setup:**
1. Configure repository secrets (AZURE_CLIENT_ID, AZURE_TENANT_ID, etc.)
2. Push code changes to `main` branch
3. Workflow automatically deploys code to function app

### Option 2: Update Scripts in Pipeline
Call update scripts from your CI/CD pipeline:

```yaml
# GitHub Actions example
- name: Update Function Code
  run: |
    ./update-function.sh --function-app "${{ secrets.AZURE_FUNCTION_APP_NAME }}"
```

```yaml
# Azure DevOps example
- task: AzureCLI@2
  inputs:
    azureSubscription: 'Your-Service-Connection'
    scriptType: 'bash'
    scriptLocation: 'inlineScript'
    inlineScript: |
      ./update-function.sh --function-app "$(FunctionAppName)"
```

---

## 📋 Quick Command Reference

### First-Time Deployment
```powershell
# PowerShell
.\deploy.ps1 -WorkspaceId "YOUR-WORKSPACE-ID"

# Bash
./deploy.sh --workspace-id "YOUR-WORKSPACE-ID"
```

### Code Update
```powershell
# PowerShell
.\update-function.ps1 -FunctionAppName "sentinel-activity-maps-func-12345"

# Bash
./update-function.sh --function-app "sentinel-activity-maps-func-12345"
```

### Azure Government
```powershell
# PowerShell - Deploy
.\deploy.ps1 -WorkspaceId "YOUR-WORKSPACE-ID" -Cloud AzureUSGovernment

# PowerShell - Update
.\update-function.ps1 -FunctionAppName "your-func" -Cloud AzureUSGovernment

# Bash - Deploy
./deploy.sh --workspace-id "YOUR-WORKSPACE-ID" --cloud AzureUSGovernment

# Bash - Update
./update-function.sh --function-app "your-func" --cloud AzureUSGovernment
```

### Cleanup
```powershell
# PowerShell
.\cleanup.ps1 -ResourceGroup "sentinel-activity-maps-rg"

# Bash
./cleanup.sh --resource-group "sentinel-activity-maps-rg"
```

### Testing After Deployment
```bash
# Wait 60 seconds for cold start, then test
FUNCTION_URL="https://sentinel-activity-maps-func-12345.azurewebsites.net"

curl $FUNCTION_URL/api/health
# Expected: {"status": "healthy", "timestamp": "..."}

curl -X POST $FUNCTION_URL/api/refresh
# Expected: {"status": "completed", "sources_processed": 2, ...}
```

---

## 🎉 Benefits

### For First-Time Users
- ✅ One-command deployment with sensible defaults
- ✅ Clear documentation with troubleshooting guidance
- ✅ Cross-platform support (Windows, Linux, macOS)
- ✅ Azure Government support out of the box

### For Developers
- ✅ Fast code updates (1-2 minutes vs 5 minutes)
- ✅ No need to redeploy infrastructure for code changes
- ✅ Easy CI/CD integration
- ✅ Clear separation between infrastructure and code deployments

### For Operations
- ✅ Idempotent scripts (safe to run multiple times)
- ✅ No secrets management (uses Managed Identity)
- ✅ Clear error messages and validation
- ✅ Easy cleanup for test environments

---

## 🔗 Related Documentation

- [DEPLOYMENT.md](DEPLOYMENT.md) - Comprehensive deployment guide
- [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md) - Quick reference checklist
- [DEPLOYMENT_SCRIPTS.md](DEPLOYMENT_SCRIPTS.md) - Script reference documentation
- [LOCAL_DEVELOPMENT.md](LOCAL_DEVELOPMENT.md) - Local testing guide
- [QUICKSTART.md](QUICKSTART.md) - Fast start guide
- [README.md](README.md) - Project overview

---

## 📊 Deployment Time Comparison

| Method | Duration | When to Use |
|--------|----------|-------------|
| **deploy.ps1 / deploy.sh** | ~5 minutes | First time, infrastructure changes, app settings changes |
| **update-function.ps1 / update-function.sh** | ~1-2 minutes | Code-only changes, development iterations |
| **GitHub Actions** | ~2-3 minutes | Automated CI/CD on push to main |
| **Manual (Azure Portal)** | ~10-15 minutes | Emergency fixes, one-off testing |

---

## ✅ Testing Checklist

After deployment or code update:

1. ⏱️ **Wait 60 seconds** for cold start
2. 🔍 **Test health endpoint**: `curl https://<func-name>.azurewebsites.net/api/health`
3. 🔄 **Test refresh endpoint**: `curl -X POST https://<func-name>.azurewebsites.net/api/refresh`
4. 📂 **Verify blob storage**: Check `datasets` container for TSV files
5. 🔒 **Verify locks**: Check `locks` container for metadata JSON files
6. 📊 **Check logs**: `az functionapp log tail --resource-group <rg> --name <func-name>`

---

## 🐛 Troubleshooting

### 404 Not Found after deployment
**Solution:** Wait 60 seconds (cold start), then try again.

### "Function app not found"
**Solution:** Verify function app name: `az functionapp list --output table`

### "Unauthorized" when querying Log Analytics
**Solution:** Verify RBAC assignment: Function App → Identity → Azure role assignments → Log Analytics Reader

### "BlobNotFound" errors
**Solution:** Verify storage containers exist and Managed Identity has "Storage Blob Data Contributor" role

### Still having issues?
1. Check function app logs: `az functionapp log tail --resource-group <rg> --name <func-name>`
2. Restart function app: `az functionapp restart --resource-group <rg> --name <func-name>`
3. Re-run deployment script (idempotent): `.\deploy.ps1 -WorkspaceId "..."`
4. See [DEPLOYMENT.md](DEPLOYMENT.md) for more troubleshooting steps

---

## 🎯 Next Steps

1. ✅ Test deployment scripts with your Azure subscription
2. ✅ Customize `api/sources.yaml` with your KQL queries
3. ✅ Set up GitHub Actions for automated deployments
4. ✅ Configure Application Insights for monitoring
5. ⏭️ Deploy Static Web App for frontend visualization
6. ⏭️ Integrate Azure Maps for geospatial visualization

---

**Questions or issues?** See [DEPLOYMENT.md](DEPLOYMENT.md) or open a GitHub issue.
