/**
 * Sentinel Activity Maps - Full Application with Threat Actors and Threat Intel
 */

let appConfig = null;
let map = null;
let threatActorsData = [];
let threatActorsByCountry = {};
let countryDataSource = null;
let threatIntelDataSource = null;
let countryLayer = null;
let threatIntelLayer = null;
let currentView = 'actors'; // 'actors' or 'intel'

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
      appConfig = window.mapConfig || config || {};
      return appConfig;
    }
  } catch (error) {
    console.warn('Error loading config from API:', error);
    appConfig = window.mapConfig || config || {};
    return appConfig;
  }
}

// Load threat actors from TSV file
async function loadThreatActors() {
  try {
    const response = await fetch('./data/threat-actors.tsv');
    const text = await response.text();
    const lines = text.trim().split('\n');
    const headers = lines[0].split('\t');
    
    threatActorsData = lines.slice(1).map(line => {
      const values = line.split('\t');
      const actor = {};
      headers.forEach((header, i) => {
        actor[header] = values[i] || '';
      });
      return actor;
    });
    
    // Group by country
    threatActorsByCountry = {};
    threatActorsData.forEach(actor => {
      const country = actor.Location || 'Unknown';
      if (!threatActorsByCountry[country]) {
        threatActorsByCountry[country] = [];
      }
      threatActorsByCountry[country].push(actor);
    });
    
    console.log('Loaded threat actors:', threatActorsData.length, 'actors from', Object.keys(threatActorsByCountry).length, 'countries');
    return threatActorsByCountry;
  } catch (error) {
    console.error('Error loading threat actors:', error);
    return {};
  }
}

// Get color based on threat actor count
function getCountryColor(count) {
  if (count >= 50) return '#ff0000';
  if (count >= 31) return '#ff8000';
  if (count >= 16) return '#ffff00';
  if (count >= 6) return '#00ff00';
  return '#0080ff';
}

// Show country details in panel
function showCountryDetails(countryName, actors) {
  const panel = document.getElementById('leftPanel');
  const title = document.getElementById('panelTitle');
  const meta = document.getElementById('panelMeta');
  const list = document.getElementById('panelList');
  
  title.textContent = countryName;
  meta.innerHTML = `<strong>${actors.length}</strong> known threat actor(s)`;
  
  let html = '<ul>';
  actors.forEach(actor => {
    html += `<li>
      <strong>${actor.Name}</strong><br/>
      <small>Motivation: ${actor.Motivation || 'Unknown'}</small><br/>
      <small>Source: ${actor.Source || 'Unknown'}</small>
    </li>`;
  });
  html += '</ul>';
  list.innerHTML = html;
  
  panel.classList.remove('hidden');
}

// Hide panel
function hidePanel() {
  document.getElementById('leftPanel').classList.add('hidden');
}

// Initialize the map
async function initMap() {
  const cfg = await loadConfig();
  const azureMapsKey = cfg.azureMapsKey || '';

  if (!azureMapsKey) {
    console.error('Azure Maps key not configured');
    alert('Azure Maps configuration missing. Please check application settings.');
    return;
  }

  console.log('Initializing map...');

  // Create the map
  map = new atlas.Map('map', {
    center: [0, 20],
    zoom: 2,
    language: 'en-US',
    style: 'road',
    authOptions: {
      authType: 'subscriptionKey',
      subscriptionKey: azureMapsKey
    }
  });

  map.events.add('ready', async function () {
    console.log('Map ready, loading data...');

    // Load threat actors
    await loadThreatActors();

    // Create data sources
    countryDataSource = new atlas.source.DataSource();
    threatIntelDataSource = new atlas.source.DataSource();
    map.sources.add(countryDataSource);
    map.sources.add(threatIntelDataSource);

    // Load world countries for polygons
    await loadCountryPolygons();

    // Load threat intel indicators
    await loadThreatIntel();

    // Create layers
    createCountryLayer();
    createThreatIntelLayer();

    // Set up UI controls
    setupControls();

    // Show threat actors by default
    showThreatActors();
    
    console.log('Map initialization complete');
  });

  map.events.add('error', function (error) {
    console.error('Map error:', error);
  });
}

// Load country polygons and color by threat actor count
async function loadCountryPolygons() {
  try {
    // Create point features for countries with threat actors
    // Using approximate center points for major countries
    const countryCoordinates = {
      'Russia': [37.6, 55.7],
      'China': [116.4, 39.9],
      'Iran': [51.4, 35.7],
      'North Korea': [125.7, 39.0],
      'Unknown': [0, 0],
      'Iraq': [44.4, 33.3],
      'Belarus': [27.6, 53.9],
      'Italy': [12.5, 41.9],
      'Lebanon': [35.5, 33.9],
      'USA': [-77.0, 38.9],
      'Pakistan': [73.1, 33.7],
      'Vietnam': [105.8, 21.0],
      'Israel': [35.2, 31.8],
      'India': [77.2, 28.6],
      'Turkey': [32.9, 39.9],
      'Gaza Strip': [34.5, 31.5],
      'Indonesia': [106.8, -6.2]
    };
    
    const features = [];
    for (const [country, actors] of Object.entries(threatActorsByCountry)) {
      const coords = countryCoordinates[country] || [0, 0];
      const count = actors.length;
      
      features.push({
        type: 'Feature',
        geometry: {
          type: 'Point',
          coordinates: coords
        },
        properties: {
          name: country,
          count: count,
          color: getCountryColor(count)
        }
      });
    }
    
    countryDataSource.add(features);
    console.log('Country features added:', features.length);
  } catch (error) {
    console.error('Error loading country data:', error);
  }
}

// Load threat intelligence indicators
async function loadThreatIntel() {
  try {
    const response = await fetch('/api/data/threat-intel');
    if (response.ok) {
      const geojson = await response.json();
      threatIntelDataSource.add(geojson);
      console.log('Threat intel loaded:', geojson.features?.length || 0, 'indicators');
    } else {
      console.warn('Failed to load threat intel:', response.status);
    }
  } catch (error) {
    console.warn('Error loading threat intel:', error);
  }
}

// Create country polygon layer
function createCountryLayer() {
  countryLayer = new atlas.layer.BubbleLayer(countryDataSource, null, {
    radius: [
      'interpolate',
      ['linear'],
      ['get', 'count'],
      1, 10,
      50, 30
    ],
    color: ['get', 'color'],
    strokeColor: '#ffffff',
    strokeWidth: 2,
    blur: 0.2
  });
  map.layers.add(countryLayer);
  
  // Add click event for countries
  map.events.add('click', countryLayer, function (e) {
    if (e.shapes && e.shapes.length > 0) {
      const props = e.shapes[0].getProperties();
      if (props.name && threatActorsByCountry[props.name]) {
        showCountryDetails(props.name, threatActorsByCountry[props.name]);
      }
    }
  });
  
  // Add hover effect
  map.events.add('mousemove', countryLayer, function() {
    map.getCanvasContainer().style.cursor = 'pointer';
  });
  map.events.add('mouseleave', countryLayer, function() {
    map.getCanvasContainer().style.cursor = 'grab';
  });
}

// Create threat intel bubble layer
function createThreatIntelLayer() {
  threatIntelLayer = new atlas.layer.BubbleLayer(threatIntelDataSource, null, {
    radius: 5,
    color: ['get', 'color', ['get', 'properties'], '#ff0000'],
    strokeColor: '#ffffff',
    strokeWidth: 1,
    blur: 0.5
  });
  map.layers.add(threatIntelLayer);
  
  // Add click event for threat intel
  map.events.add('click', threatIntelLayer, function (e) {
    if (e.shapes && e.shapes.length > 0) {
      const props = e.shapes[0].getProperties();
      showThreatIntelDetails(props);
    }
  });
}

// Show threat intel details
function showThreatIntelDetails(props) {
  const panel = document.getElementById('leftPanel');
  const title = document.getElementById('panelTitle');
  const meta = document.getElementById('panelMeta');
  const list = document.getElementById('panelList');
  
  title.textContent = 'Threat Indicator';
  meta.innerHTML = `<strong>IP:</strong> ${props.ObservableValue || 'N/A'}<br/>
    <strong>Type:</strong> ${props.Type || 'N/A'}<br/>
    <strong>Confidence:</strong> ${props.Confidence || 'N/A'}`;
  list.innerHTML = `<p>${props.Description || 'No description available'}</p>`;
  
  panel.classList.remove('hidden');
}

// Show threat actors view
function showThreatActors() {
  currentView = 'actors';
  if (countryLayer) countryLayer.setOptions({ visible: true });
  if (threatIntelLayer) threatIntelLayer.setOptions({ visible: false });
  document.getElementById('countryLegend').classList.remove('hidden');
  console.log('Showing threat actors by country');
}

// Show threat intel view
function showThreatIntel() {
  currentView = 'intel';
  if (countryLayer) countryLayer.setOptions({ visible: false });
  if (threatIntelLayer) threatIntelLayer.setOptions({ visible: true });
  document.getElementById('countryLegend').classList.add('hidden');
  console.log('Showing threat intelligence indicators');
}

// Setup UI controls
function setupControls() {
  // Panel hide buttons
  document.getElementById('panelHideBtn')?.addEventListener('click', hidePanel);
  document.getElementById('floatingPanelCloseBtn')?.addEventListener('click', hidePanel);
  
  // Show threat actors
  document.getElementById('showThreatMapBtn')?.addEventListener('click', showThreatActors);
  document.getElementById('showActorsBtn')?.addEventListener('click', showThreatActors);
  
  // Show threat intel
  document.getElementById('showIntelBtn')?.addEventListener('click', showThreatIntel);
  
  console.log('UI controls setup complete');
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', initMap);
