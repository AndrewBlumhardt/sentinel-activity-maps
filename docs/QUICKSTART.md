# Quick Start - 5 Minute Setup

Get the function running locally in 5 minutes (no Azure resources needed for basic testing).

## Step 1: Install Prerequisites (2 minutes)

Open PowerShell as Administrator:

```powershell
# Install Python 3.11
winget install Python.Python.3.11

# Install Azure Functions Core Tools
winget install Microsoft.Azure.FunctionsCoreTools

# Restart PowerShell to refresh PATH
```

## Step 2: Setup Project (1 minute)

```powershell
# Navigate to project
cd c:\repos\sentinel-activity-maps\api

# Create virtual environment
python -m venv .venv

# Activate it
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

## Step 3: Test Without Azure (1 minute)

```powershell
# Run local tests (no Azure connection needed)
python test_local.py
```

You should see:
```
✅ All tests passed! Your function is ready for local development.
```

## Step 4: Start Function Locally (1 minute)

```powershell
# Start the function
func start
```

You'll see:
```
Functions:
  health: [GET] http://localhost:7071/api/health
  refresh: [GET,POST] http://localhost:7071/api/refresh
```

## Step 5: Test the Health Endpoint

Open a **new PowerShell window**:

```powershell
# Test health endpoint
Invoke-RestMethod http://localhost:7071/api/health
```

Response:
```json
{
  "status": "healthy",
  "timestamp": "2026-02-07T12:34:56Z",
  "sources_configured": 2
}
```

## 🎉 Success!

Your function is running locally. The `/api/health` endpoint works without any Azure resources.

## Next Steps

### To Test with Real Azure Data:

1. **Get Azure credentials** from Azure Portal:
   - Log Analytics Workspace ID
   - Storage Account URL

2. **Update `local.settings.json`**:
   ```json
   {
     "Values": {
       "LOG_ANALYTICS_WORKSPACE_ID": "your-workspace-id",
       "STORAGE_ACCOUNT_URL": "https://your-storage.blob.core.windows.net"
     }
   }
   ```

3. **Login to Azure**:
   ```powershell
   az login
   ```

4. **Test refresh endpoint**:
   ```powershell
   Invoke-RestMethod "http://localhost:7071/api/refresh?force=true"
   ```

### To Understand the Code:

1. **Read the architecture**: Open `docs\architecture.md`
2. **Review main function**: Open `api\function_app.py` in VS Code
3. **Check data sources**: Edit `api\sources.yaml` to see query configuration
4. **Explore modules**: Browse `api\shared\` folder

### To Deploy to Azure:

See [README.md](README.md) section "Azure Setup & Permissions"

## Troubleshooting

**"python not found"**
- Close and reopen PowerShell after installing Python
- Or use full path: `C:\Users\YourName\AppData\Local\Programs\Python\Python311\python.exe`

**"func not found"**
- Close and reopen PowerShell after installing Azure Functions Core Tools
- Or install via npm: `npm install -g azure-functions-core-tools@4`

**"Module not found" when running func start**
- Make sure virtual env is activated: `.\.venv\Scripts\Activate.ps1`
- Reinstall dependencies: `pip install -r requirements.txt`

**"Cannot find sources.yaml"**
- Make sure you're in the `api` folder: `cd c:\repos\sentinel-activity-maps\api`

## Quick Command Reference

```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Run tests
python test_local.py

# Start function
func start

# Test health (in another terminal)
curl http://localhost:7071/api/health

# Stop function
# Press Ctrl+C in the terminal running func start

# Deactivate virtual environment
deactivate
```

---

Need more details? See [LOCAL_DEVELOPMENT.md](LOCAL_DEVELOPMENT.md)
