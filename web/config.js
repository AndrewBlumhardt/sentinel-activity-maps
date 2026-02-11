// Azure Maps and Storage configuration
// This file is auto-generated during deployment
const config = {
    // Azure Maps subscription key
    azureMapsKey: window.ENV?.AZURE_MAPS_SUBSCRIPTION_KEY || '',
    
    // Storage account URL for GeoJSON data
    storageAccountUrl: window.ENV?.STORAGE_ACCOUNT_URL || 'https://sentinelmapsstore.blob.core.windows.net',
    
    // Container name for datasets
    datasetsContainer: window.ENV?.STORAGE_CONTAINER_DATASETS || 'datasets',
    
    // GeoJSON file name for threat intel indicators
    geoJsonFileName: 'threat-intel-indicators.geojson',
    
    // Full URL to threat intel GeoJSON
    get threatIntelGeoJsonUrl() {
        return `${this.storageAccountUrl}/${this.datasetsContainer}/${this.geoJsonFileName}`;
    },
    
    // Local threat actors TSV file (fallback)
    threatActorsTsvUrl: './data/threat-actors.tsv',
    
    // Map configuration
    map: {
        center: [0, 20],
        zoom: 2,
        style: 'road',
        language: 'en-US'
    }
};

// Make config globally available
window.mapConfig = config;
