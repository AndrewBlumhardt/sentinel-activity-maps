# Deployment Scripts - Summary

This document summarizes the deployment automation added to the Sentinel Activity Maps project.

## 📦 What Was Added

### Deployment Scripts

1. **[deploy.ps1](deploy.ps1)** - PowerShell deployment script (Windows)
   - Automated resource provisioning
   - RBAC configuration
   - Function code deployment
   - ~5 minute deployment time

2. **[deploy.sh](deploy.sh)** - Bash deployment script (Linux/macOS/WSL)
   - Identical functionality to PowerShell version
   - Cross-platform compatible
   - Uses standard Azure CLI commands

3. **[update-function.ps1](update-function.ps1)** - PowerShell code update script
   - Updates only function code (no infrastructure changes)
   - Faster than full deployment (~1-2 minutes)
   - Automatic restart and warmup
   - Cloud support (AzureCloud, AzureUSGovernment)

4. **[update-function.sh](update-function.sh)** - Bash code update script
   - Cross-platform code-only updates
   - Identical to PowerShell version
   - For development iterations and CI/CD

5. **[cleanup.ps1](cleanup.ps1)** - PowerShell cleanup script
   - Removes all Azure resources
   - Safety confirmation prompt
   - Background deletion

6. **[cleanup.sh](cleanup.sh)** - Bash cleanup script
   - Cross-platform resource cleanup
   - Identical to PowerShell version

### Documentation

1. **[DEPLOYMENT.md](DEPLOYMENT.md)** - Comprehensive deployment guide
   - Automated deployment instructions
   - Step-by-step manual deployment
   - Post-deployment configuration
   - Troubleshooting guide
   - ~2000 lines of detailed documentation

2. **[DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md)** - Quick reference
   - Pre-deployment checklist
   - Post-deployment verification steps
   - Common issues and fixes
   - Quick command reference

3. **[README.md](README.md)** - Updated with deployment section
   - Quick deploy commands at top
   - Links to detailed guides
   - Streamlined instructions

## 🚀 How to Use

### Quick Deploy (First Time)

**Windows:**
```powershell
.\deploy.ps1 -WorkspaceId "YOUR-WORKSPACE-ID"
```

**Linux/macOS:**
```bash
chmod +x deploy.sh
./deploy.sh --workspace-id "YOUR-WORKSPACE-ID"
```

### Code Updates (After Initial Deployment)

**Windows:**
```powershell
.\update-function.ps1 -FunctionAppName "sentinel-activity-maps-func-12345"
```

**Linux/macOS:**
```bash
chmod +x update-function.sh
./update-function.sh --function-app "sentinel-activity-maps-func-12345"
```

**Note:** Allow 30-60 seconds after code deployment for the function to fully start (cold start). If you get 404 errors immediately after deployment, wait a minute and try again.

### Azure Government Cloud

All scripts support Azure Government (GCC/GCC-High):

**PowerShell:**
```powershell
# Full deployment
.\deploy.ps1 -WorkspaceId "YOUR-WORKSPACE-ID" -Cloud AzureUSGovernment

# Code update
.\update-function.ps1 -FunctionAppName "your-func" -Cloud AzureUSGovernment
```

**Bash:**
```bash
# Full deployment
./deploy.sh --workspace-id "YOUR-WORKSPACE-ID" --cloud AzureUSGovernment

# Code update
./update-function.sh --function-app "your-func" --cloud AzureUSGovernment
```

### Custom Configuration

Both deployment scripts support custom parameters:

**PowerShell:**
```powershell
.\deploy.ps1 `
    -WorkspaceId "12345678-1234-1234-1234-123456789012" `
    -ResourceGroupName "my-rg" `
    -Location "westus2" `
    -StorageAccountName "mystorageacct" `
    -FunctionAppName "myfunctionapp"
```

**Bash:**
```bash
./deploy.sh \
    --workspace-id "12345678-1234-1234-1234-123456789012" \
    --resource-group "my-rg" \
    --location "westus2" \
    --storage-account "mystorageacct" \
    --function-app "myfunctionapp"
```

## 🏗️ What Gets Created

The deployment scripts create the following Azure resources:

1. **Resource Group**
   - Default: `sentinel-activity-maps-rg`
   - Location: `eastus` (configurable)

2. **Storage Account**
   - SKU: Standard_LRS
   - Kind: StorageV2
   - TLS 1.2 minimum
   - Public blob access disabled
   - Containers:
     - `datasets` - TSV output files
     - `locks` - Metadata and locking

3. **App Service Plan**
   - Type: Consumption (Y1)
   - OS: Linux
   - SKU: Dynamic

4. **Function App**
   - Runtime: Python 3.11
   - Functions Version: 4
   - System-assigned Managed Identity enabled
   - Application settings configured

5. **RBAC Assignments**
   - Storage Blob Data Contributor (on storage account)
   - Note: Log Analytics Reader must be assigned manually

## ⚙️ Configuration

### Environment Variables Set

The scripts automatically configure these application settings:

| Setting | Value |
|---------|-------|
| `LOG_ANALYTICS_WORKSPACE_ID` | Your workspace ID |
| `STORAGE_ACCOUNT_URL` | `https://<storage-account>.blob.core.windows.net` |
| `STORAGE_CONTAINER_DATASETS` | `datasets` |
| `STORAGE_CONTAINER_LOCKS` | `locks` |
| `DEFAULT_REFRESH_INTERVAL_SECONDS` | `300` |
| `DEFAULT_QUERY_TIME_WINDOW_HOURS` | `24` |
| `INCREMENTAL_OVERLAP_MINUTES` | `10` |

### Managed Identity

The scripts enable system-assigned managed identity and assign:
- ✅ Storage Blob Data Contributor (automated)
- ⚠️ Log Analytics Reader (manual - requires workspace permissions)

## 📝 Manual Steps Required

### 1. Get Workspace ID

Find your Log Analytics Workspace ID:

**Azure Portal:**
1. Navigate to your Log Analytics Workspace
2. Go to **Properties**
3. Copy the **Workspace ID** (GUID)

**Azure CLI:**
```bash
az monitor log-analytics workspace show \
    --resource-group <workspace-rg> \
    --workspace-name <workspace-name> \
    --query customerId -o tsv
```

### 2. Assign Log Analytics Reader Role

After deployment, assign the role manually:

**Azure Portal:**
1. Go to Log Analytics Workspace → Access control (IAM)
2. Add role assignment → Log Analytics Reader
3. Select Managed Identity → Function App → Your function

**Azure CLI:**
```bash
# Get principal ID from deployment output
PRINCIPAL_ID="<from-deployment-output>"

az role assignment create \
    --assignee $PRINCIPAL_ID \
    --role "Log Analytics Reader" \
    --scope "/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.OperationalInsights/workspaces/<workspace>"
```

## 🧪 Testing

After deployment, verify everything works:

```bash
# Test health
curl https://<function-app>.azurewebsites.net/api/health

# Trigger refresh
curl -X POST https://<function-app>.azurewebsites.net/api/refresh

# Check logs
az functionapp log tail --name <function-app> --resource-group <rg>

# List output files
az storage blob list \
    --container-name datasets \
    --account-name <storage-account> \
    --auth-mode login
```

## 🧹 Cleanup

Remove all resources:

**PowerShell:**
```powershell
.\cleanup.ps1 -ResourceGroupName "sentinel-activity-maps-rg"
```

**Bash:**
```bash
./cleanup.sh --resource-group "sentinel-activity-maps-rg"
```

## 🔄 CI/CD Integration

For automated deployments on git push, see:
- [.github/workflows/deploy-function.yml](.github/workflows/deploy-function.yml)
- Configure GitHub secrets for OIDC authentication
- Deployment runs automatically on push to `main`

## 🛡️ Security Features

The deployment scripts implement these security best practices:

✅ **Managed Identity** - No connection strings or keys
✅ **RBAC** - Principle of least privilege
✅ **TLS 1.2+** - Enforced on all services
✅ **Private storage** - No public blob access
✅ **Encrypted** - All data encrypted at rest
✅ **Audit logs** - All access logged via Azure Monitor

## 📚 Documentation Structure

```
/
├── README.md                      # Main readme with quick start
├── DEPLOYMENT.md                  # Detailed deployment guide
├── DEPLOYMENT_CHECKLIST.md        # Quick reference checklist
├── LOCAL_DEVELOPMENT.md           # Local development setup
├── QUICKSTART.md                  # 5-minute quick start
├── deploy.ps1                     # PowerShell deployment
├── deploy.sh                      # Bash deployment
├── cleanup.ps1                    # PowerShell cleanup
├── cleanup.sh                     # Bash cleanup
└── docs/
    └── architecture.md            # Architecture details
```

## 💡 Tips for Users

1. **First time deploying?** Use the automated scripts - they handle all the complexity
2. **Need control?** Follow the manual steps in DEPLOYMENT.md
3. **Testing locally first?** See QUICKSTART.md for local development
4. **Production deployment?** Set up CI/CD with GitHub Actions
5. **Something went wrong?** Check DEPLOYMENT.md troubleshooting section

## 🎯 Next Steps

After successful deployment:

1. ✅ Verify health endpoint responds
2. ✅ Assign Log Analytics Reader role
3. ✅ Trigger first refresh
4. ✅ Verify TSV files created
5. 📊 Deploy Static Web App frontend (separate project)
6. 🔄 Set up scheduled refreshes (Logic App or Timer trigger)
7. 📈 Configure Application Insights dashboards
8. 🚨 Set up Azure Monitor alerts

## 🤝 Contributing

To improve these deployment scripts:

1. Test on your environment
2. Report issues or suggest improvements
3. Submit pull requests with enhancements
4. Update documentation if behavior changes

## 📞 Support

- **Issues:** Report bugs via GitHub Issues
- **Questions:** Open a discussion on GitHub
- **Security:** Report vulnerabilities via GitHub Security Advisories

---

**Created:** February 2026  
**Version:** 1.0  
**Compatibility:** Azure CLI 2.x, PowerShell 7+, Bash 4+
