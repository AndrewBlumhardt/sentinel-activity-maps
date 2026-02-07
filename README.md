# Sentinel Activity Maps - Function Backend

Python-based Azure Functions backend for the Sentinel Activity Maps project. This function queries Azure Log Analytics (Microsoft Sentinel) and exports threat intelligence data to Azure Blob Storage as TSV files for consumption by the frontend Static Web App.

## 🎯 Purpose

- **HTTP-triggered** Azure Function that refreshes threat intelligence datasets
- **Managed Identity** authentication (no secrets)
- **Blob-based locking** for multi-user safety
- **Incremental queries** with watermark tracking
- **Throttling** to prevent redundant work
- **Extensible** via YAML configuration (no code changes to add data sources)

## 📁 Project Structure

```
api/
├── function_app.py              # Main Azure Functions app with endpoints
├── host.json                    # Function runtime configuration
├── requirements.txt             # Python dependencies
├── local.settings.json          # Local development settings (template)
├── sources.yaml                 # Data source configuration (KQL queries)
└── shared/                      # Shared modules
    ├── __init__.py
    ├── config_loader.py         # YAML config parser
    ├── log_analytics_client.py  # Log Analytics query executor
    ├── blob_storage.py          # Blob operations + locking
    ├── tsv_writer.py            # TSV formatter
    └── refresh_policy.py        # Throttling + incremental logic

.github/workflows/
├── deploy-function.yml          # CI/CD deployment pipeline
└── lint-test.yml               # Linting and testing (optional)

docs/
└── architecture.md              # Detailed architecture documentation
```

## 🚀 Quick Start

### Prerequisites

1. **Azure Resources**:
   - Azure Function App (Python 3.11, Linux)
   - Log Analytics Workspace (with Sentinel data)
   - Storage Account with two containers: `datasets` and `locks`

2. **Local Development Tools**:
   - Python 3.11+
   - [Azure Functions Core Tools](https://learn.microsoft.com/azure/azure-functions/functions-run-local)
   - Azure CLI (for authentication)

### Local Development Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/AndrewBlumhardt/sentinel-activity-maps.git
   cd sentinel-activity-maps/api
   ```

2. **Install dependencies**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure local settings**:
   ```bash
   cp local.settings.json local.settings.json.bak
   # Edit local.settings.json with your values
   ```

   Required settings:
   ```json
   {
     "Values": {
       "LOG_ANALYTICS_WORKSPACE_ID": "<workspace-guid>",
       "STORAGE_ACCOUNT_URL": "https://<account>.blob.core.windows.net",
       "STORAGE_CONTAINER_DATASETS": "datasets",
       "STORAGE_CONTAINER_LOCKS": "locks"
     }
   }
   ```

4. **Login to Azure** (for local Managed Identity simulation):
   ```bash
   az login
   az account set --subscription <subscription-id>
   ```

5. **Run locally**:
   ```bash
   func start
   ```

   Test endpoints:
   - Health: `http://localhost:7071/api/health`
   - Refresh: `http://localhost:7071/api/refresh`

## 🔧 Configuration

### Adding a New Data Source

Edit `api/sources.yaml` and add a new entry:

```yaml
sources:
  - id: my_new_source          # Unique identifier (used in locks/metadata)
    name: "My Data Source"     # Display name
    enabled: true              # Set to false to disable
    refresh_interval_seconds: 300  # Minimum time between refreshes
    query_time_window_hours: 24    # Default query window
    incremental: true          # Use watermark-based incremental queries
    incremental_overlap_minutes: 10  # Overlap to catch late-arriving events
    output_filename: "my-data.tsv"   # Output TSV filename
    kql_query: |
      MyTable
      | where TimeGenerated >= ago({time_window}h)
      | project TimeGenerated, Column1, Column2
      | order by TimeGenerated desc
    columns:                   # Column order in TSV output
      - TimeGenerated
      - Column1
      - Column2
```

**Deploy** the updated configuration (no code changes needed):
```bash
func azure functionapp publish <function-app-name>
```

### Environment Variables

Set these in Azure Function App Configuration:

| Variable | Description | Example |
|----------|-------------|---------|
| `LOG_ANALYTICS_WORKSPACE_ID` | Workspace GUID | `12345678-1234-1234-1234-123456789012` |
| `STORAGE_ACCOUNT_URL` | Blob storage URL | `https://mystorageacct.blob.core.windows.net` |
| `STORAGE_CONTAINER_DATASETS` | Container for TSV files | `datasets` |
| `STORAGE_CONTAINER_LOCKS` | Container for locks/metadata | `locks` |
| `DEFAULT_REFRESH_INTERVAL_SECONDS` | Default throttle interval | `300` |
| `DEFAULT_QUERY_TIME_WINDOW_HOURS` | Default query window | `24` |
| `INCREMENTAL_OVERLAP_MINUTES` | Overlap for incremental queries | `10` |

## 🔐 Azure Setup & Permissions

### 1. Create Resources

```bash
RESOURCE_GROUP="rg-sentinel-activity-maps"
LOCATION="eastus"
FUNCTION_APP_NAME="sentinel-activity-maps-func"
STORAGE_ACCOUNT="sentinelmapssa"  # Must be globally unique
WORKSPACE_ID="<your-log-analytics-workspace-id>"

# Create resource group
az group create --name $RESOURCE_GROUP --location $LOCATION

# Create storage account
az storage account create \
  --name $STORAGE_ACCOUNT \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION \
  --sku Standard_LRS

# Create containers
STORAGE_CONN=$(az storage account show-connection-string \
  --name $STORAGE_ACCOUNT --resource-group $RESOURCE_GROUP --query connectionString -o tsv)

az storage container create --name datasets --connection-string $STORAGE_CONN
az storage container create --name locks --connection-string $STORAGE_CONN

# Create Function App
az functionapp create \
  --resource-group $RESOURCE_GROUP \
  --name $FUNCTION_APP_NAME \
  --storage-account $STORAGE_ACCOUNT \
  --consumption-plan-location $LOCATION \
  --runtime python \
  --runtime-version 3.11 \
  --functions-version 4 \
  --os-type Linux
```

### 2. Enable Managed Identity

```bash
az functionapp identity assign \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP

# Get the principal ID
MI_PRINCIPAL_ID=$(az functionapp identity show \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --query principalId -o tsv)
```

### 3. Assign RBAC Permissions

**Log Analytics Reader** (for querying):
```bash
WORKSPACE_RESOURCE_ID="/subscriptions/<subscription-id>/resourceGroups/<workspace-rg>/providers/Microsoft.OperationalInsights/workspaces/<workspace-name>"

az role assignment create \
  --assignee $MI_PRINCIPAL_ID \
  --role "Log Analytics Reader" \
  --scope $WORKSPACE_RESOURCE_ID
```

**Storage Blob Data Contributor** (for writing TSVs):
```bash
STORAGE_RESOURCE_ID=$(az storage account show \
  --name $STORAGE_ACCOUNT \
  --resource-group $RESOURCE_GROUP \
  --query id -o tsv)

az role assignment create \
  --assignee $MI_PRINCIPAL_ID \
  --role "Storage Blob Data Contributor" \
  --scope $STORAGE_RESOURCE_ID
```

### 4. Configure Function App Settings

```bash
az functionapp config appsettings set \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --settings \
    "LOG_ANALYTICS_WORKSPACE_ID=$WORKSPACE_ID" \
    "STORAGE_ACCOUNT_URL=https://${STORAGE_ACCOUNT}.blob.core.windows.net" \
    "STORAGE_CONTAINER_DATASETS=datasets" \
    "STORAGE_CONTAINER_LOCKS=locks" \
    "DEFAULT_REFRESH_INTERVAL_SECONDS=300" \
    "DEFAULT_QUERY_TIME_WINDOW_HOURS=24" \
    "INCREMENTAL_OVERLAP_MINUTES=10"
```

## 🚢 Deployment

### Option 1: GitHub Actions (Recommended)

1. **Setup OIDC (Federated Credentials)** - No secrets needed:
   ```bash
   # Create Azure AD App Registration
   APP_ID=$(az ad app create --display-name "sentinel-activity-maps-github" --query appId -o tsv)
   
   # Create service principal
   az ad sp create --id $APP_ID
   SP_OBJECT_ID=$(az ad sp show --id $APP_ID --query id -o tsv)
   
   # Assign Contributor role to Function App
   az role assignment create \
     --assignee $APP_ID \
     --role Contributor \
     --scope "/subscriptions/<subscription-id>/resourceGroups/$RESOURCE_GROUP"
   
   # Create federated credential
   az ad app federated-credential create \
     --id $APP_ID \
     --parameters '{
       "name": "github-sentinel-activity-maps",
       "issuer": "https://token.actions.githubusercontent.com",
       "subject": "repo:AndrewBlumhardt/sentinel-activity-maps:ref:refs/heads/main",
       "audiences": ["api://AzureADTokenExchange"]
     }'
   ```

2. **Add GitHub Secrets**:
   - `AZURE_CLIENT_ID` = `$APP_ID`
   - `AZURE_TENANT_ID` = Your tenant ID
   - `AZURE_SUBSCRIPTION_ID` = Your subscription ID

3. **Update workflow** (`.github/workflows/deploy-function.yml`):
   - Set `AZURE_FUNCTIONAPP_NAME` to your function app name

4. **Deploy**:
   ```bash
   git add .
   git commit -m "Initial function implementation"
   git push origin main
   ```

### Option 2: Azure CLI (Manual)

```bash
cd api
func azure functionapp publish $FUNCTION_APP_NAME
```

### Option 3: VS Code

1. Install [Azure Functions extension](https://marketplace.visualstudio.com/items?itemName=ms-azuretools.vscode-azurefunctions)
2. Right-click `api` folder → "Deploy to Function App..."
3. Select your function app

## 📡 API Reference

### `GET/POST /api/refresh`

Refresh threat intelligence datasets.

**Query Parameters**:
- `source_id` (optional): Refresh specific source only
- `force` (optional): Bypass throttling (`true`/`false`)
- `correlation_id` (optional): Tracking ID for logs

**Response Codes**:
- `200` - Successfully refreshed data
- `204` - No refresh needed (throttled)
- `202` - Refresh in progress (locked by another process)
- `429` - Too many requests (rate limited)
- `500` - Internal error

**Example**:
```bash
# Refresh all sources
curl https://sentinel-activity-maps-func.azurewebsites.net/api/refresh

# Refresh specific source
curl https://sentinel-activity-maps-func.azurewebsites.net/api/refresh?source_id=signin_failures

# Force refresh (bypass throttling)
curl https://sentinel-activity-maps-func.azurewebsites.net/api/refresh?force=true
```

**Response**:
```json
{
  "message": "Refreshed 2/2 sources",
  "refreshed_count": 2,
  "total_sources": 2,
  "results": [
    {
      "source_id": "signin_failures",
      "status": "refreshed",
      "row_count": 1234,
      "output_file": "signin-failures.tsv"
    }
  ],
  "correlation_id": "abc123"
}
```

### `GET /api/health`

Health check endpoint.

**Response**:
```json
{
  "status": "healthy",
  "timestamp": "2026-02-07T12:34:56Z",
  "sources_configured": 2
}
```

## 🧪 Testing

### Manual Testing

```bash
# Test health endpoint
curl http://localhost:7071/api/health

# Test refresh (requires Azure credentials)
curl http://localhost:7071/api/refresh?force=true

# Check generated files in Blob Storage
az storage blob list \
  --container-name datasets \
  --account-name $STORAGE_ACCOUNT \
  --output table
```

### Unit Tests (TODO)

```bash
cd api
pip install pytest pytest-cov
pytest tests/ --cov=shared --cov-report=term-missing
```

## 🔍 Observability

### Logs

View logs in Azure:
```bash
az functionapp log tail --name $FUNCTION_APP_NAME --resource-group $RESOURCE_GROUP
```

View logs in Application Insights:
```kusto
traces
| where cloud_RoleName == "sentinel-activity-maps-func"
| where message contains "correlation_id"
| order by timestamp desc
```

### Metrics

- **Execution Count**: Total function invocations
- **Execution Duration**: Time per refresh
- **Success Rate**: Percentage of successful refreshes

### Correlation IDs

Pass `correlation_id` query parameter to track requests across logs:
```bash
curl "https://...azurewebsites.net/api/refresh?correlation_id=frontend-abc123"
```

## 🛠️ Troubleshooting

### Common Issues

1. **"Failed to initialize Log Analytics client"**
   - Ensure Managed Identity is enabled
   - Verify RBAC assignment for Log Analytics Reader role
   - Check `LOG_ANALYTICS_WORKSPACE_ID` is correct

2. **"Failed to write TSV to blob"**
   - Verify Storage Blob Data Contributor role assignment
   - Check `STORAGE_ACCOUNT_URL` format (must include `https://`)
   - Ensure containers exist (`datasets`, `locks`)

3. **"Query failed with status"**
   - Verify KQL query syntax in `sources.yaml`
   - Check query time window (too large may timeout)
   - Review Log Analytics workspace data retention

4. **"Could not acquire lock"**
   - Another process is refreshing the same source
   - Wait for lock to expire (60 seconds) or check for stuck leases

### Debug Mode

Enable verbose logging:
```bash
# Local development
export LOGGING_LEVEL=DEBUG
func start

# Azure Function App
az functionapp config appsettings set \
  --name $FUNCTION_APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --settings "LOGGING_LEVEL=DEBUG"
```

## 📚 Additional Resources

- [Architecture Documentation](docs/architecture.md)
- [Azure Functions Python Developer Guide](https://learn.microsoft.com/azure/azure-functions/functions-reference-python)
- [Azure Monitor Query Client Library](https://learn.microsoft.com/python/api/overview/azure/monitor-query-readme)
- [Azure Blob Storage SDK](https://learn.microsoft.com/python/api/overview/azure/storage-blob-readme)
- [Managed Identity Overview](https://learn.microsoft.com/entra/identity/managed-identities-azure-resources/overview)

## 🤝 Contributing

### Development Workflow

1. Create a feature branch: `git checkout -b feature/my-feature`
2. Make changes and test locally: `func start`
3. Commit with descriptive messages
4. Push and create a pull request
5. CI/CD runs linting and tests automatically

### Code Style

- Follow PEP 8 (enforced by Black and Flake8)
- Add docstrings to all public functions
- Use type hints where appropriate
- Keep functions focused and testable

## 📝 Changelog

### v1.0.0 (2026-02-07)
- Initial implementation with Python Azure Functions
- Managed Identity authentication for Log Analytics and Blob Storage
- Blob-based locking for multi-user safety
- Server-side throttling with configurable intervals
- Incremental query support with watermark tracking
- Extensible YAML-based configuration
- GitHub Actions CI/CD pipeline with OIDC
- Comprehensive documentation

## 📄 License

MIT License - See LICENSE file for details

## 👤 Author

Andrew Blumhardt
- GitHub: [@AndrewBlumhardt](https://github.com/AndrewBlumhardt)

---

**Need help?** Open an issue on GitHub or check the [architecture documentation](docs/architecture.md) for more details.
