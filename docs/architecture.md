# Sentinel Activity Maps - Function Backend Architecture

## Overview

The Sentinel Activity Maps backend is a Python-based Azure Functions application that queries Azure Log Analytics (Sentinel) and exports threat intelligence data to Azure Blob Storage in TSV format for consumption by the frontend Azure Static Web App.

## Architecture Components

### 1. Azure Functions (HTTP-Triggered)

**Primary Endpoint**: `/api/refresh`
- Triggered by SWA frontend or scheduled job
- Returns quickly with status codes (no data payload)
- Implements server-side throttling to prevent redundant queries

**Health Endpoint**: `/api/health`
- Basic health check for monitoring
- Returns configuration status

### 2. Data Flow

```
SWA Frontend → HTTP Request → Azure Function
                                    ↓
                              Check Throttle
                                    ↓
                              Acquire Blob Lock
                                    ↓
                              Query Log Analytics (KQL)
                                    ↓
                              Format as TSV
                                    ↓
                              Write to Blob Storage
                                    ↓
                              Update Metadata
                                    ↓
                              Release Lock
                                    ↓
                              Return Status
```

### 3. Storage Layout

#### Datasets Container (`datasets`)
- `signin-failures.tsv` - Failed sign-in attempts
- `threat-intel-indicators.tsv` - Threat intelligence indicators
- *(more files added via sources.yaml)*

#### Locks/Metadata Container (`locks`)
- `signin_failures.lock` - Blob lease for locking
- `signin_failures-metadata.json` - Query metadata
- `threat_intel_indicators.lock`
- `threat_intel_indicators-metadata.json`

### 4. Authentication

**Managed Identity (System-Assigned)**
- Function App → Log Analytics (Reader role)
- Function App → Blob Storage (Storage Blob Data Contributor)
- No secrets in code or configuration

### 5. Throttling & Locking

**Server-Side Throttling**
- Reads metadata to check last refresh time
- Enforces minimum interval (default 5 minutes, configurable per source)
- Returns 204 if too soon, avoiding redundant work

**Blob Lease Locking**
- Uses Azure Blob leases as distributed locks
- Prevents concurrent refreshes of same dataset
- Lease duration: 60 seconds (auto-releases on failure)
- Returns 202 if locked by another process

### 6. Incremental Updates

**Watermark Strategy**
- Tracks `last_query_watermark` in metadata JSON
- Queries from watermark with configurable overlap (default 10 minutes)
- Handles late-arriving events in Log Analytics
- First run: Full time window (default 24 hours)

### 7. Extensibility

**Adding New Data Sources**
1. Edit `api/sources.yaml`
2. Add new source definition with:
   - Unique `id`
   - KQL query with `{time_window}` placeholder
   - Column definitions
   - Refresh interval
   - Output filename
3. Deploy function (no code changes needed)

## Configuration

### Environment Variables
- `LOG_ANALYTICS_WORKSPACE_ID` - Workspace GUID
- `STORAGE_ACCOUNT_URL` - Blob storage URL
- `STORAGE_CONTAINER_DATASETS` - Container for TSV files
- `STORAGE_CONTAINER_LOCKS` - Container for locks/metadata
- `DEFAULT_REFRESH_INTERVAL_SECONDS` - Default throttle interval
- `DEFAULT_QUERY_TIME_WINDOW_HOURS` - Default query window
- `INCREMENTAL_OVERLAP_MINUTES` - Overlap for incremental queries

### Sources Configuration (`sources.yaml`)
```yaml
sources:
  - id: source_identifier
    name: "Display Name"
    enabled: true
    refresh_interval_seconds: 300
    query_time_window_hours: 24
    incremental: true
    incremental_overlap_minutes: 10
    output_filename: "output.tsv"
    kql_query: |
      KQL query here with {time_window} placeholder
    columns:
      - Column1
      - Column2
```

## Deployment

### Prerequisites
1. Azure Function App (Python 3.11, Consumption or Premium plan)
2. System-Assigned Managed Identity enabled on Function App
3. Log Analytics Workspace with data ingestion
4. Storage Account with two containers (`datasets`, `locks`)

### RBAC Assignments
```bash
# Function MI → Log Analytics Reader
az role assignment create \
  --assignee <function-mi-principal-id> \
  --role "Log Analytics Reader" \
  --scope <workspace-resource-id>

# Function MI → Storage Blob Data Contributor
az role assignment create \
  --assignee <function-mi-principal-id> \
  --role "Storage Blob Data Contributor" \
  --scope <storage-account-resource-id>
```

### CI/CD
- GitHub Actions workflow: `.github/workflows/deploy-function.yml`
- OIDC/Federated credentials (recommended) or Publish Profile
- Automatic deployment on push to `main` branch

## Observability

### Logging
- Structured logging with correlation IDs
- Application Insights integration (via host.json)
- Log levels: INFO (default), DEBUG (detailed queries)

### Response Headers
- `X-Correlation-ID` - Request tracking
- `X-Refreshed-Count` - Number of sources updated

### Status Codes
- `200` - Data refreshed successfully
- `204` - No refresh needed (throttled)
- `202` - Refresh in progress (locked)
- `429` - Too many requests (rate limited)
- `500` - Internal error

## Performance Considerations

### Multi-User Safety
- Blob leases prevent duplicate work
- Metadata-based throttling reduces Log Analytics query load
- Lock expiration (60s) prevents deadlocks

### SWA Fast Boot
- SWA reads existing TSVs immediately (no wait)
- Background refresh updates data asynchronously
- Frontend polling (1-5 minutes) triggers refreshes

### Cost Optimization
- Idle function (no scheduled triggers)
- Pay-per-execution pricing
- Incremental queries reduce Log Analytics costs
- Throttling prevents redundant queries

## Security

### Current Model (Public Demo)
- Anonymous auth level (no authentication required)
- Suitable for public-facing demo

### Private Deployment Option
- Change `auth_level` to `FUNCTION` in function_app.py
- Distribute function key to authorized SWA instances
- Add Private Endpoints to Storage Account
- Add Private Link to Function App
- Configure VNet integration for Function App

## Future Enhancements

1. **Deduplication** - Remove duplicate rows in incremental mode
2. **Delta Compression** - Only send changed records
3. **Query Caching** - Cache results for very frequent requests
4. **Metrics Export** - Prometheus/OpenTelemetry metrics
5. **Unit Tests** - pytest suite for shared modules
