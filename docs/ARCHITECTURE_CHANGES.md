# Architecture Changes - Event-Driven Refresh

## Summary

Converted from timer-based polling to event-driven, file-age-based refresh model.

## Key Changes

### 1. Removed Timer Trigger
- **Before**: Function runs every 10 minutes automatically
- **After**: Function only runs when called via HTTP (by web app or API)

### 2. File-Age-Based Refresh
- **Before**: Always queries Sentinel on every call
- **After**: 
  - First call: Check if files exist → if not, pull 15 days + enrich
  - Subsequent calls: Check file age → if < 24 hours, return cached data
  - If > 24 hours: Refresh in temp file, then atomic replace

### 3. Configuration Changes
**sources.yaml**:
- Removed: `refresh_interval_seconds`
- Added: `refresh_threshold_hours: 24` (configurable per source)
- Added: `key_vault_name` (optional, for storing MaxMind key)

### 4. Key Vault Integration
- MaxMind license key now stored in Azure Key Vault
- Falls back to environment variable if Key Vault not configured
- Uses Managed Identity for authentication

### 5. Simplified Locking
- No distributed locking needed (single function instance)
- Temp file pattern ensures atomic replacement
- File operations are naturally serialized

## File-Age-Based Refresh Logic

```
HTTP Request → /api/refresh
   ↓
Check if TSV file exists
   ↓
If NOT exists:
   → Pull 15 days from Sentinel
   → Enrich with MaxMind
   → Save TSV + GeoJSON
   → Return stats
   ↓
If exists, check last_modified
   ↓
If age < refresh_threshold_hours (24h):
   → Return "cached, no refresh needed"
   → Include file stats in response
   ↓
If age >= refresh_threshold_hours:
   → Pull incremental data (since watermark)
   → Enrich new IPs only
   → Save to temp files (.tmp)
   → Atomic rename temp → production
   → Return stats
```

## Benefits

1. **Idle when not needed**: Function doesn't run unless called
2. **Smart caching**: Avoids unnecessary Sentinel queries
3. **Cost effective**: Only pulls data when stale
4. **Web-app friendly**: Fast response for cached data
5. **Configurable**: Easy to adjust refresh threshold per source
6. **Atomic updates**: No partial file states
7. **Secure**: Secrets in Key Vault, not environment variables

## Response Format

```json
{
  "source_id": "threat_intel_indicators",
  "status": "cached" | "refreshed" | "initial_load",
  "file_age_hours": 12.5,
  "refresh_threshold_hours": 24,
  "row_count": 14863,
  "last_modified": "2026-02-09T10:30:00Z",
  "geo_enriched": 14845,
  "geojson_features": 14845
}
```

## Configuration

**sources.yaml**:
```yaml
geo_provider: "maxmind"
key_vault_name: "kv-sentinel-maps"  # Optional

sources:
  - id: threat_intel_indicators
    enabled: true
    refresh_threshold_hours: 24  # Configurable!
    query_time_window_hours: 360
    auto_enrich_geo: true
    auto_generate_geojson: true
```

## Future: Multiple Sources

Ready for adding more sources with different refresh patterns:

```yaml
sources:
  - id: threat_intel_indicators
    refresh_threshold_hours: 24  # Static data, refresh daily
    
  - id: signin_failures
    refresh_threshold_hours: 1  # Dynamic data, refresh hourly
    
  - id: device_network_events
    refresh_threshold_hours: 4  # Semi-dynamic, refresh every 4h
```

## Key Vault Setup

```powershell
# Create Key Vault
$kvName = "kv-sentinel-maps-$(Get-Random -Minimum 1000 -Maximum 9999)"
az keyvault create --name $kvName --resource-group "rg-sentinel-activity-maps" --location "eastus"

# Store MaxMind key
az keyvault secret set --vault-name $kvName --name "MAXMIND-LICENSE-KEY" --value "your-key-here"

# Grant Function App access
$functionPrincipalId = (az functionapp identity show --name "func-sentinel-activity-maps" --resource-group "rg-sentinel-activity-maps" --query principalId -o tsv)
az keyvault set-policy --name $kvName --object-id $functionPrincipalId --secret-permissions get list

# Update sources.yaml
key_vault_name: "kv-sentinel-maps-1234"
```

## Migration Notes

- Existing files remain valid - no data loss
- First call after deployment will check file age
- If files are fresh (<24h), they'll be used as-is
- No need to delete existing data

## Testing

```powershell
# Initial call (file doesn't exist)
Invoke-RestMethod "https://func-sentinel-activity-maps.azurewebsites.net/api/refresh"
# → Status: "initial_load", pulls 15 days

# Subsequent call (< 24h)
Invoke-RestMethod "https://func-sentinel-activity-maps.azurewebsites.net/api/refresh"
# → Status: "cached", returns existing file stats

# Force refresh
Invoke-RestMethod "https://func-sentinel-activity-maps.azurewebsites.net/api/refresh?force=true"
# → Status: "refreshed", pulls incremental data

# After 24h
Invoke-RestMethod "https://func-sentinel-activity-maps.azurewebsites.net/api/refresh"
# → Status: "refreshed", automatic incremental refresh
```
