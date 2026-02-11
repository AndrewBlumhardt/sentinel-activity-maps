/**
 * Sentinel Activity Maps - Main Application
 * Simple threat intelligence visualization using Azure Maps
 */

// Load configuration
const azureMapsKey = window.mapConfig?.azureMapsKey || config?.azureMapsKey || '';
const geoJsonUrl = window.mapConfig?.threatIntelGeoJsonUrl || config?.threatIntelGeoJsonUrl || '';

// Initialize the map
async function initMap() {
  if (!azureMapsKey) {
    console.error('Azure Maps key not configured');
    alert('Azure Maps configuration missing. Please check application settings.');
    return;
  }

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
    if (geoJsonUrl) {
      try {
        console.log('Loading threat intelligence data from:', geoJsonUrl);
        const response = await fetch(geoJsonUrl);
        if (response.ok) {
          const geojson = await response.json();
          dataSource.add(geojson);
          console.log('Threat intelligence data loaded');
        } else {
          console.warn('Failed to load threat data:', response.status);
        }
      } catch (error) {
        console.warn('Error loading threat data:', error);
      }
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
