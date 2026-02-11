# Local Development Guide

## Prerequisites Check

Open a **new PowerShell window** and run these commands:

```powershell
# Check Python version (need 3.11+)
python --version

# Check if Azure Functions Core Tools is installed
func --version

# Check Azure CLI
az --version
```

### Install Missing Tools

**Python 3.11**:
- Download from: https://www.python.org/downloads/
- Or use winget: `winget install Python.Python.3.11`

**Azure Functions Core Tools**:
- Download from: https://learn.microsoft.com/azure/azure-functions/functions-run-local
- Or use npm: `npm install -g azure-functions-core-tools@4`
- Or use winget: `winget install Microsoft.Azure.FunctionsCoreTools`

**Azure CLI** (for local auth):
- Download from: https://learn.microsoft.com/cli/azure/install-azure-cli-windows
- Or use winget: `winget install Microsoft.AzureCLI`

## Setup Steps

### 1. Create Virtual Environment

```powershell
cd c:\repos\sentinel-activity-maps\api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install Dependencies

```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure Local Settings

```powershell
# Copy the template (if not already done)
if (-not (Test-Path "local.settings.json")) {
    Copy-Item "local.settings.json" "local.settings.json.bak"
}
```

Edit `local.settings.json` with your Azure credentials:

```json
{
  "IsEncrypted": false,
  "Values": {
    "AzureWebJobsStorage": "UseDevelopmentStorage=true",
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "LOG_ANALYTICS_WORKSPACE_ID": "YOUR-WORKSPACE-ID-HERE",
    "STORAGE_ACCOUNT_URL": "https://YOUR-STORAGE-ACCOUNT.blob.core.windows.net",
    "STORAGE_CONTAINER_DATASETS": "datasets",
    "STORAGE_CONTAINER_LOCKS": "locks",
    "DEFAULT_REFRESH_INTERVAL_SECONDS": "300",
    "DEFAULT_QUERY_TIME_WINDOW_HOURS": "24",
    "INCREMENTAL_OVERLAP_MINUTES": "10"
  }
}
```

### 4. Login to Azure (for local Managed Identity simulation)

```powershell
az login
az account set --subscription "YOUR-SUBSCRIPTION-NAME-OR-ID"
```

## Running Locally

### Start the Function App

```powershell
cd c:\repos\sentinel-activity-maps\api
func start
```

You should see output like:
```
Azure Functions Core Tools
Core Tools Version:       4.x.x
Function Runtime Version: 4.x.x

Functions:
  health: [GET] http://localhost:7071/api/health
  refresh: [GET,POST] http://localhost:7071/api/refresh
```

### Test Endpoints

**Open a new terminal** and test:

```powershell
# Test health endpoint
Invoke-RestMethod http://localhost:7071/api/health

# Test refresh endpoint (read-only check)
Invoke-RestMethod "http://localhost:7071/api/refresh?force=true"
```

## Understanding the Code

### Entry Point: `function_app.py`

This is the main file with two HTTP endpoints:

1. **`/api/health`** - Simple health check
   - Returns: Configuration status, number of sources
   - No Azure resources required

2. **`/api/refresh`** - Main refresh endpoint
   - Query params: `source_id`, `force`, `correlation_id`
   - Returns: Refresh status (200, 204, 202, 429, 500)

### Code Flow for `/api/refresh`:

```
1. Parse parameters (source_id, force flag)
2. Load configuration from sources.yaml
3. For each enabled source:
   a. Check if refresh needed (throttling)
   b. Try to acquire blob lock
   c. Calculate query timespan (incremental vs full)
   d. Execute KQL query via Log Analytics
   e. Format results as TSV
   f. Write to Blob Storage
   g. Update metadata (watermark, row count)
   h. Release lock
4. Return summary response
```

### Shared Modules (`shared/` folder):

- **`config_loader.py`** - Reads `sources.yaml`, validates config
- **`log_analytics_client.py`** - Connects to Log Analytics, executes KQL
- **`blob_storage.py`** - Read/write TSV + metadata, blob leasing for locks
- **`tsv_writer.py`** - Format query results as TSV
- **`refresh_policy.py`** - Throttling logic, watermark tracking

## Testing Without Azure Resources

### Option 1: Mock the Azure Clients

Create `api/test_local.py`:

```python
import sys
sys.path.insert(0, '.')

from shared.config_loader import ConfigLoader
from shared.tsv_writer import TSVWriter

# Test configuration loading
print("Testing configuration loader...")
config = ConfigLoader()
sources = config.get_enabled_sources()
print(f"✓ Loaded {len(sources)} sources:")
for src in sources:
    print(f"  - {src.id}: {src.name}")

# Test TSV formatting
print("\nTesting TSV writer...")
test_data = [
    {'Name': 'Alice', 'Age': 30, 'City': 'NYC'},
    {'Name': 'Bob', 'Age': 25, 'City': 'LA'}
]
tsv = TSVWriter.write_tsv(test_data)
print("✓ Generated TSV:")
print(tsv)

# Test parsing back
parsed = TSVWriter.parse_tsv(tsv)
print(f"✓ Parsed {len(parsed)} rows back")

print("\n✅ All tests passed!")
```

Run it:
```powershell
cd c:\repos\sentinel-activity-maps\api
.\.venv\Scripts\Activate.ps1
python test_local.py
```

### Option 2: Test Individual Modules

```powershell
cd api
python -c "from shared.config_loader import ConfigLoader; c=ConfigLoader(); print(f'Loaded {len(c.get_all_sources())} sources')"
```

### Option 3: Use Azure Storage Emulator (Azurite)

For testing blob operations without real Azure Storage:

```powershell
# Install Azurite
npm install -g azurite

# Start emulator
azurite --silent --location c:\azurite --debug c:\azurite\debug.log

# Update local.settings.json to use emulator
# AzureWebJobsStorage is already set to "UseDevelopmentStorage=true"
```

## Debugging in VS Code

### 1. Install Extensions
- **Azure Functions** (ms-azuretools.vscode-azurefunctions)
- **Python** (ms-python.python)

### 2. Select Python Interpreter
- Press `Ctrl+Shift+P`
- Type "Python: Select Interpreter"
- Choose `.venv\Scripts\python.exe`

### 3. Debug Configuration

VS Code should auto-detect the function. Press **F5** to start debugging.

Or create `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Attach to Python Functions",
      "type": "python",
      "request": "attach",
      "port": 9091,
      "preLaunchTask": "func: host start"
    }
  ]
}
```

### 4. Set Breakpoints

- Open `function_app.py`
- Click left of line numbers to set breakpoints
- Press **F5** to start debugging
- Call the endpoint with curl or browser

## Common Issues

### "Module not found" errors
```powershell
# Make sure virtual env is activated
.\.venv\Scripts\Activate.ps1

# Reinstall dependencies
pip install -r requirements.txt
```

### "Cannot connect to Log Analytics"
- Ensure `az login` was successful
- Check `LOG_ANALYTICS_WORKSPACE_ID` is correct
- Verify you have Reader permissions on the workspace

### "Cannot write to Blob Storage"
- Check `STORAGE_ACCOUNT_URL` format (include `https://`)
- Ensure containers `datasets` and `locks` exist
- Verify Storage Blob Data Contributor permissions

### Function doesn't start
```powershell
# Check for syntax errors
python -m py_compile function_app.py

# Check Azure Functions Core Tools version
func --version  # Should be 4.x
```

## Next Steps

1. **Review the code** - Start with `function_app.py`, then explore `shared/` modules
2. **Test locally** - Run `func start` and call endpoints
3. **Modify sources.yaml** - Add your own KQL queries
4. **Add logging** - Enhance debug output as needed
5. **Deploy to Azure** - Once working locally, deploy with CI/CD

## Quick Reference

### Useful Commands

```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Run function locally
func start

# Test health
curl http://localhost:7071/api/health

# Test refresh
curl "http://localhost:7071/api/refresh?force=true"

# Check logs
# Logs appear in terminal where `func start` is running

# Deactivate virtual environment
deactivate
```

### Key Files to Understand

1. **`function_app.py`** (200 lines) - Start here, HTTP endpoints
2. **`sources.yaml`** (60 lines) - Data source configuration
3. **`shared/config_loader.py`** (100 lines) - Config parsing
4. **`shared/log_analytics_client.py`** (120 lines) - KQL execution
5. **`shared/blob_storage.py`** (200 lines) - Storage + locking
6. **`shared/refresh_policy.py`** (140 lines) - Throttling logic

### Project Stats
- **Total Lines**: ~1,900 lines
- **Python Files**: 7 files
- **Dependencies**: 6 packages
- **Endpoints**: 2 (health, refresh)
