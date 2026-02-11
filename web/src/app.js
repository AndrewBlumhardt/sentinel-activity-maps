/**
 * Sentinel Activity Maps - Main Application
 * Simple threat intelligence visualization using Azure Maps
 */

let appConfig = null;

// Fetch configuration from API
async function loadConfig() {
  try {
    const response = await fetch('/api/config');
    if (response.ok) {
      appConfig = await response.json();
      console.log('Configuration loaded from API');
      return appConfig;
    } else {
      console.warn('Failed to load config from API, using fallback');
      // Fallback to static config
      appConfig = window.mapConfig || config || {};
      return appConfig;
    }
  } catch (error) {
    console.warn('Error loading config from API:', error);
    // Fallback to static config
    appConfig = window.mapConfig || config || {};
    return appConfig;
  }
}

// Initialize the map
async function initMap() {
  // Load configuration first
  const cfg = await loadConfig();
  
  const azureMapsKey = cfg.azureMapsKey || '';
  const dataApiUrl = '/api/data/threat-intel';  // Use API proxy instead of direct storage access

  if (!azureMapsKey) {
    console.error('Azure Maps key not configured');
    alert('Azure Maps configuration missing. Please check application settings.');
    return;
  }

  console.log('Initializing map with config:', {
    hasKey: !!azureMapsKey,
    dataUrl: dataApiUrl
  });

  // Create the map
  const map = new atlas.Map('map', {
    center: [0, 20],
    zoom: 2,
    language: 'en-US',
    authOptions: {
      authType: 'subscriptionKey',
      subscriptionKey: azureMapsKey
    }
  });

  // Wait for map to be ready
  map.events.add('ready', async function () {
    console.log('Map initialized successfully');

    // Add data source for threat intelligence
    const dataSource = new atlas.source.DataSource();
    map.sources.add(dataSource);

    // Try to load GeoJSON data
    try {
      console.log('Loading threat intelligence data from:', dataApiUrl);
      const response = await fetch(dataApiUrl);
      if (response.ok) {
        const geojson = await response.json();
        dataSource.add(geojson);
        console.log('Threat intelligence data loaded:', geojson.features?.length || 0, 'features');
      } else {
        console.warn('Failed to load threat data:', response.status);
      }
    } catch (error) {
      console.warn('Error loading threat data:', error);
    }

    // Add bubble layer for threat indicators
    map.layers.add(new atlas.layer.BubbleLayer(dataSource, null, {
      radius: 5,
      color: '#ff0000',
      strokeColor: '#ffffff',
      strokeWidth: 1,
      blur: 0.5
    }));

    console.log('Map ready');
  });

  map.events.add('error', function (error) {
    console.error('Map error:', error);
  });
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', initMap);
