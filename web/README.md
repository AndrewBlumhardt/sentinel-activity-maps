# Sentinel Activity Maps - Web Application

Azure Static Web App displaying threat intelligence data on an interactive map using Azure Maps.

## Features

- **Interactive Azure Maps**: Visualize threat intelligence indicators with clustering
- **Real-time Data**: Loads GeoJSON data from Azure Blob Storage
- **Threat Actor Intelligence**: Display known threat actor locations
- **Responsive Design**: Works on desktop and mobile devices

## Architecture

- **Frontend**: Vanilla JavaScript with Azure Maps SDK
- **Data Source**: GeoJSON file (`threat-intel-indicators.geojson`) from Azure Blob Storage
- **Hosting**: Azure Static Web Apps (Standard SKU)
- **Map Provider**: Azure Maps

## Files

- `index.html` - Main application page
- `src/app.js` - Application logic and Azure Maps integration
- `styles/app.css` - Application styling
- `config.js` - Configuration (auto-generated during deployment)
- `config.sample.js` - Sample configuration template
- `data/threat-actors.tsv` - Threat actor reference data
- `staticwebapp.config.json` - SWA routing and configuration

## Configuration

The application uses environment variables set in Azure Static Web Apps:

- `AZURE_MAPS_SUBSCRIPTION_KEY` - Azure Maps subscription key
- `STORAGE_ACCOUNT_URL` - Azure Storage account URL
- `STORAGE_CONTAINER_DATASETS` - Blob container name (default: datasets)

## Deployment

The app is automatically deployed via GitHub Actions when changes are pushed to the `web/` directory.

### Manual Deployment

1. Create Azure Static Web App (Standard SKU):
   ```bash
   az staticwebapp create \
     --name swa-sentinel-activity-maps \
     --resource-group rg-sentinel-activity-maps \
     --location westus2 \
     --sku Standard
   ```

2. Get deployment token:
   ```bash
   az staticwebapp secrets list \
     --name swa-sentinel-activity-maps \
     --resource-group rg-sentinel-activity-maps \
     --query properties.apiKey -o tsv
   ```

3. Add token to GitHub secrets as `AZURE_STATIC_WEB_APPS_API_TOKEN`

4. Push to main branch to trigger deployment

## Local Development

1. Copy `config.sample.js` to `config.js` and update with your keys
2. Serve the web directory using any HTTP server:
   ```bash
   # Using Python
   python -m http.server 8000
   
   # Using Node.js http-server
   npx http-server -p 8000
   ```
3. Open http://localhost:8000 in your browser

## Data Flow

1. Azure Function pulls threat intel from Sentinel → enriches with geo data → saves GeoJSON to Blob
2. Static Web App loads GeoJSON from Blob Storage
3. Azure Maps displays indicators with clustering and heatmap

## Browser Support

- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)

Requires JavaScript enabled and modern browser with ES6 support.
