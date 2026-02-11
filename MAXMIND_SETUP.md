# MaxMind GeoLite2 Setup Guide

This guide explains how to set up MaxMind GeoLite2 for IP geolocation enrichment.

## Why MaxMind?

- ✅ **Free for commercial use** (with attribution)
- ✅ **Full geolocation data**: latitude, longitude, city, country
- ✅ **Local database**: Fast lookups, no API rate limits
- ✅ **Industry standard**: Used by security tools worldwide

## Setup Steps

### 1. Create Free MaxMind Account

1. Go to https://www.maxmind.com/en/geolite2/signup
2. Fill out the registration form
3. Verify your email address
4. Log in to your account

### 2. Generate License Key

1. Go to **Account** → **Manage License Keys**
2. Click **Generate new license key**
3. Name: `sentinel-activity-maps`
4. **Important**: Select "**No**" for "Will this key be used for GeoIP Update?"
   (We'll download via API, not the updater tool)
5. Click **Confirm**
6. **Copy the license key immediately** - it's only shown once!

### 3. Configure Azure Function

Add the license key to your Function App settings:

**Option A: Using Azure Portal**
1. Go to your Function App in Azure Portal
2. Settings → Environment variables → App settings
3. Click **+ Add**
4. Name: `MAXMIND_LICENSE_KEY`
5. Value: `<your-license-key>`
6. Click **Apply**

**Option B: Using Azure CLI**
```powershell
az functionapp config appsettings set `
    --name "func-sentinel-activity-maps" `
    --resource-group "rg-sentinel-activity-maps" `
    --settings MAXMIND_LICENSE_KEY="<your-license-key>"
```

**Option C: Using deployment script**
Update `deploy.ps1` before running:
```powershell
$maxmindLicenseKey = "<your-license-key>"  # Line ~120
```

### 4. Configure Geo Provider

Edit `api/sources.yaml`:

```yaml
# For MaxMind (full coordinates):
geo_provider: "maxmind"

# For Azure Maps (country-only):
geo_provider: "azure_maps"
```

### 5. Deploy

Deploy the updated code:

```powershell
# Full deployment
.\deploy.ps1

# Or code-only update
.\update-function.ps1
```

## How It Works

1. **First run**: Function downloads GeoLite2-City database (~50MB) to `/tmp`
2. **Database cached**: Subsequent lookups are instant (local database)
3. **Updates**: Database expires after 30 days - will auto-download new version

## Database Location

- **Azure Functions**: `/tmp/GeoLite2-City.mmdb` (ephemeral, auto-downloads)
- **Local testing**: Same path, persists between runs

## Switching Between Providers

You can switch between MaxMind and Azure Maps at any time:

**MaxMind (full coordinates)**:
```yaml
geo_provider: "maxmind"
```
- Requires: `MAXMIND_LICENSE_KEY`
- Returns: country, city, latitude, longitude
- Best for: Mapping, detailed geo analysis

**Azure Maps (country-only)**:
```yaml
geo_provider: "azure_maps"
```
- Requires: `AZURE_MAPS_SUBSCRIPTION_KEY`
- Returns: country only
- Best for: Simple country-level filtering, compliance

## Testing

Test geolocation lookups:

```powershell
# Test a specific IP
Invoke-RestMethod -Method GET "https://func-sentinel-activity-maps.azurewebsites.net/api/test-geo-lookup?ip=8.8.8.8"

# Run full refresh with enrichment
Invoke-RestMethod -Method POST "https://func-sentinel-activity-maps.azurewebsites.net/api/refresh?force=true"
```

## Attribution Requirement

MaxMind GeoLite2 is free but requires attribution. Add to your documentation:

> This product includes GeoLite2 data created by MaxMind, available from https://www.maxmind.com

## Troubleshooting

**"MaxMind database not found and no license key to download"**
- Ensure `MAXMIND_LICENSE_KEY` is set in Function App settings
- Restart the Function App after adding the setting

**"geoip2 library not installed"**
- Ensure `requirements.txt` includes `geoip2>=4.7.0`
- Use `--build-remote true` when deploying (see `update-function.ps1`)

**Database download fails**
- Check license key is correct
- Ensure Function App can reach `download.maxmind.com`
- Check Azure Function logs for details

**Lookups return None**
- Private IPs (10.x, 192.168.x, etc.) won't have geolocation
- Some infrastructure IPs may not be in the database

## License

- **GeoLite2**: Creative Commons Attribution-ShareAlike 4.0 International License
- **Free for**: Personal, commercial, non-profit use
- **Requirement**: Attribution
- **Details**: https://dev.maxmind.com/geoip/geolite2-free-geolocation-data

## Additional Resources

- MaxMind Account: https://www.maxmind.com/en/account
- GeoLite2 Documentation: https://dev.maxmind.com/geoip/geolite2-free-geolocation-data
- geoip2 Python Library: https://github.com/maxmind/GeoIP2-python
