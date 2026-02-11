import { parseTSV } from "../data/tsv.js";

/* global atlas */

/*
Threat Actor Heatmap Overlay (Country-level)

User-facing overview:
- We load the threat actor TSV file.
- We count how many actors are associated with each country (Location column).
- We place ONE point per country (at an approximate centroid).
- We render those points using Azure Maps' native HeatMapLayer.
  The heatmap uses the per-country count as the "weight" so higher counts appear hotter.
*/

// Minimal centroids so we can render without geocoding/boundary calls.
// Expand over time (or later add Lat/Lon to TSV and bypass this).
const COUNTRY_CENTROIDS = {
  "Russia": [100.0, 60.0],
  "China": [104.0, 35.0],
  "Iran": [53.0, 32.0],
  "Iraq": [43.7, 33.2],
  "Lebanon": [35.9, 33.9],
  "North Korea": [127.5, 40.3],
  "Vietnam": [108.3, 14.1],
  "Pakistan": [69.3, 30.4],
  "India": [78.9, 20.6],
  "Turkey": [35.2, 39.0],
  "Italy": [12.6, 41.9],
  "Belarus": [27.9, 53.7],
  "Ukraine": [31.2, 48.4],
  "Brazil": [-51.9, -14.2],
  "Mexico": [-102.6, 23.6],
  "Nigeria": [8.7, 9.1],
  "Israel": [34.9, 31.0],
  "United Arab Emirates": [54.3, 24.3],
  "Austria": [14.6, 47.5],
  "France": [2.2, 46.2],
  "Spain": [-3.7, 40.4],
  "Tunisia": [9.5, 33.9],
  "Algeria": [2.6, 28.0],
  "Saudi Arabia": [45.1, 24.0],
  "Libya": [17.2, 26.3],
  "Georgia": [43.4, 42.3],
  "Armenia": [45.0, 40.1],
  "Taiwan": [121.0, 23.7],
  "Indonesia": [113.9, -0.8],
  "Kazakhstan": [66.9, 48.0],
  "Syria": [38.5, 35.0],
  "Venezuela": [-66.6, 6.4],
  "Philippines": [122.0, 12.9],
  "Singapore": [103.8, 1.35],
  "Romania": [25.0, 45.9],
  "Uzbekistan": [64.6, 41.4],
  "Canada": [-106.3, 56.1],
  "United States of America": [-98.6, 39.8],
  "United States": [-98.6, 39.8],
  "Türkiye": [35.2, 39.0],
  "Gaza": [34.3, 31.35],
  "Korea": [127.8, 36.5]
};

// ISO 3166-1 alpha-2 country codes for fetching boundaries
const COUNTRY_ISO_CODES = {
  "Russia": "RU",
  "China": "CN",
  "Iran": "IR",
  "Iraq": "IQ",
  "Lebanon": "LB",
  "North Korea": "KP",
  "Vietnam": "VN",
  "Pakistan": "PK",
  "India": "IN",
  "Turkey": "TR",
  "Türkiye": "TR",
  "Italy": "IT",
  "Belarus": "BY",
  "Ukraine": "UA",
  "Brazil": "BR",
  "Mexico": "MX",
  "Nigeria": "NG",
  "Israel": "IL",
  "United Arab Emirates": "AE",
  "Austria": "AT",
  "France": "FR",
  "Spain": "ES",
  "Tunisia": "TN",
  "Algeria": "DZ",
  "Saudi Arabia": "SA",
  "Libya": "LY",
  "Georgia": "GE",
  "Armenia": "AM",
  "Taiwan": "TW",
  "Indonesia": "ID",
  "Kazakhstan": "KZ",
  "Syria": "SY",
  "Venezuela": "VE",
  "Philippines": "PH",
  "Singapore": "SG",
  "Romania": "RO",
  "Uzbekistan": "UZ",
  "Canada": "CA",
  "United States of America": "US",
  "United States": "US",
  "Gaza": "PS",
  "Korea": "KR",
  "South Korea": "KR",
  "Germany": "DE",
  "Poland": "PL",
  "United Kingdom": "GB",
  "The Netherlands": "NL"
};

// Local bounding box coordinates for countries (to avoid API calls)
// Format: [minLon, minLat, maxLon, maxLat]
const COUNTRY_BOUNDS = {
  "Russia": [19.25, 41.15, 190.0, 81.86],
  "China": [73.68, 18.16, 134.77, 53.56],
  "Iran": [44.03, 25.06, 63.33, 39.78],
  "Iraq": [38.79, 29.07, 48.57, 37.38],
  "Lebanon": [35.10, 33.05, 36.62, 34.69],
  "North Korea": [124.32, 37.67, 130.67, 43.01],
  "Vietnam": [102.14, 8.18, 109.47, 23.39],
  "Pakistan": [60.87, 23.69, 77.84, 37.13],
  "India": [68.18, 6.75, 97.40, 35.51],
  "Turkey": [25.67, 35.82, 44.83, 42.11],
  "Italy": [6.63, 35.49, 18.52, 47.09],
  "Belarus": [23.18, 51.26, 32.77, 56.17],
  "Ukraine": [22.14, 44.39, 40.18, 52.38],
  "Brazil": [-73.98, -33.75, -28.85, 5.27],
  "Mexico": [-118.40, 14.54, -86.71, 32.72],
  "Nigeria": [2.67, 4.27, 14.68, 13.89],
  "Israel": [34.27, 29.50, 35.88, 33.34],
  "United Arab Emirates": [51.58, 22.63, 56.38, 26.08],
  "Austria": [9.53, 46.37, 17.16, 49.02],
  "France": [-5.14, 41.33, 9.56, 51.09],
  "Spain": [-18.17, 27.64, 4.32, 43.79],
  "Tunisia": [7.52, 30.24, 11.60, 37.54],
  "Algeria": [-8.67, 18.97, 12.00, 37.09],
  "Saudi Arabia": [34.50, 16.38, 55.67, 32.16],
  "Libya": [9.39, 19.50, 25.15, 33.17],
  "Georgia": [39.96, 41.05, 46.71, 43.59],
  "Armenia": [43.45, 38.84, 46.63, 41.30],
  "Taiwan": [120.04, 21.90, 122.01, 25.30],
  "Indonesia": [95.01, -11.01, 141.02, 6.08],
  "Kazakhstan": [46.49, 40.94, 87.36, 55.44],
  "Syria": [35.73, 32.31, 42.38, 37.23],
  "Venezuela": [-73.35, 0.65, -59.80, 12.20],
  "Philippines": [116.93, 4.64, 126.60, 21.12],
  "Singapore": [103.64, 1.16, 104.01, 1.47],
  "Romania": [20.26, 43.62, 29.71, 48.27],
  "Uzbekistan": [55.99, 37.18, 73.13, 45.59],
  "Canada": [-141.00, 41.68, -52.62, 83.11],
  "United States": [-179.15, 18.91, -66.95, 71.39],
  "United States of America": [-179.15, 18.91, -66.95, 71.39],
  "Gaza": [34.22, 31.22, 34.57, 31.59],
  "Korea": [124.61, 33.11, 131.87, 38.61],
  "South Korea": [124.61, 33.11, 131.87, 38.61],
  "Germany": [5.87, 47.27, 15.04, 55.06],
  "Poland": [14.12, 49.00, 24.15, 54.84],
  "United Kingdom": [-8.62, 49.96, 1.77, 60.84],
  "The Netherlands": [3.36, 50.75, 7.23, 53.55]
};

const IDS = {
  source: "taByCountrySource",
  heatLayer: "taHeatLayer",
  polygonLayer: "taCountryPolygonLayer",
  outlineLayer: "taCountryOutlineLayer"
};

let enabled = false;
let currentMode = null;
let countryData = null;

export async function toggleThreatActorsHeatmap(map, turnOn, mode = "heatmap", onCountryClick = null) {
  
  if (turnOn) {
    if (enabled && currentMode === mode) return;
    // Ensure clean state before enabling
    if (enabled) {
      disable(map);
      enabled = false;
      currentMode = null;
      // Give Azure Maps time to fully cleanup
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    await enable(map, mode, onCountryClick);
    enabled = true;
    currentMode = mode;
  } else {
    if (!enabled) return;
    disable(map);
    enabled = false;
    currentMode = null;
    // Give Azure Maps time to fully cleanup
    await new Promise(resolve => setTimeout(resolve, 100));
  }
}

async function enable(map, mode, onCountryClick) {
  // Remove existing layers (but keep source to reuse)
  try {
    if (map.layers.getLayerById(IDS.outlineLayer)) map.layers.remove(IDS.outlineLayer);
    if (map.layers.getLayerById(IDS.polygonLayer)) map.layers.remove(IDS.polygonLayer);
    if (map.layers.getLayerById(IDS.heatLayer)) map.layers.remove(IDS.heatLayer);
  } catch (e) {
    console.warn('Error removing layers:', e);
  }

  // Get or create data source (reuse if exists to avoid "already added" error)
  let dataSource = map.sources.getById(IDS.source);
  if (dataSource) {
    // Clear existing data from source
    dataSource.clear();
  } else {
    // Create new source and add to map
    dataSource = new atlas.source.DataSource(IDS.source);
    map.sources.add(dataSource);
  }

  // Load threat actor data from TSV file
  const resp = await fetch("/data/threat-actors.tsv", { cache: "no-store" });
  if (!resp.ok) throw new Error("Could not load /data/threat-actors.tsv");

  const rows = parseTSV(await resp.text());

  // Count actors by country
  const counts = new Map();
  const actorsByCountry = new Map();

  for (const r of rows) {
    let country = (r.Location || "")
      .replace(/\u00A0/g, " ")
      .replace(/\s+/g, " ")
      .trim();

    if (!country) continue;

    if (country === "United States of America" || country === "USA" || country === "US" || country === "U.S.") {
      country = "United States";
    }

    counts.set(country, (counts.get(country) || 0) + 1);
    
    if (!actorsByCountry.has(country)) {
      actorsByCountry.set(country, []);
    }
    actorsByCountry.get(country).push(r);
  }

  countryData = { counts, actorsByCountry };

  const maxCount = Math.max(...counts.values());

  if (mode === "country") {
    // Country polygon view - fetch actual country boundaries from GeoJSON
    let labelSource;  // Declare outside try block for proper scope
    try {
      // Fetch world countries GeoJSON from reliable CDN source
      const geoResponse = await fetch('https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json');
      if (!geoResponse.ok) throw new Error('Failed to load country boundaries');
      
      const topoData = await geoResponse.json();
      
      // Convert TopoJSON to GeoJSON using Atlas built-in support
      // TopoJSON is more compact, we need to convert it
      const geoJsonResponse = await fetch('https://unpkg.com/world-atlas@2/countries-50m.json');
      const worldData = await geoJsonResponse.json();
      
      // Simple approach: Use a lightweight GeoJSON directly
      const countriesResponse = await fetch('https://raw.githubusercontent.com/datasets/geo-countries/master/data/countries.geojson');
      const countriesGeoJSON = await countriesResponse.json();
      
      // Build lookup map of country names to their GeoJSON features
      const countryGeometries = new Map();
      countriesGeoJSON.features.forEach(feature => {
        const name = feature.properties.ADMIN || feature.properties.name;
        if (name) {
          countryGeometries.set(name, feature.geometry);
        }
      });
      
      // Create features for countries with threat actors
      const features = [];
      for (const [country, count] of counts.entries()) {
        // Try to find matching geometry
        let geometry = countryGeometries.get(country);
        
        // Try common name variations if direct match fails
        if (!geometry) {
          const variations = [
            country.replace('United States of America', 'United States'),
            country.replace('United States', 'United States of America'),
            country.replace('The Netherlands', 'Netherlands'),
            country.replace('Korea', 'South Korea'),
            country.replace('South Korea', 'Republic of Korea')
          ];
          
          for (const variant of variations) {
            geometry = countryGeometries.get(variant);
            if (geometry) break;
          }
        }
        
        // Fall back to bounding box if no geometry found
        if (!geometry) {
          const bounds = COUNTRY_BOUNDS[country];
          if (bounds) {
            const [minLon, minLat, maxLon, maxLat] = bounds;
            geometry = {
              type: "Polygon",
              coordinates: [[
                [minLon, maxLat],
                [maxLon, maxLat],
                [maxLon, minLat],
                [minLon, minLat],
                [minLon, maxLat]
              ]]
            };
          } else {
            console.warn(`No geometry found for country: ${country}`);
            continue;
          }
        }
        
        // Create feature with threat actor metadata
        const feature = new atlas.data.Feature(geometry, {
          country,
          count,
          normalizedCount: count / maxCount,
          actors: actorsByCountry.get(country)
        });
        
        features.push(feature);
      }
      
      if (features.length === 0) {
        console.error("Could not create any country boundaries");
        return;
      }

      // Add country polygons to data source
      dataSource.add(features);
      
      // Create separate point data source for labels (one point per country at centroid)
      labelSource = new atlas.source.DataSource(IDS.source + '_labels');
      for (const [country, count] of counts.entries()) {
        const centroid = COUNTRY_CENTROIDS[country];
        if (centroid) {
          labelSource.add(new atlas.data.Feature(
            new atlas.data.Point(centroid),
            { country, count }
          ));
        }
      }
      map.sources.add(labelSource);
    } catch (error) {
      console.error('Error loading country boundaries:', error);
      return;
    }

    // Create polygon fill layer with logical color scheme based on threat actor count
    const polygonLayer = new atlas.layer.PolygonLayer(dataSource, IDS.polygonLayer, {
      fillColor: [
        "step",
        ["get", "count"],
        "#0080ff",  // 1-5 actors: Blue
        6,  "#00ff00",  // 6-15 actors: Green
        16, "#ffff00",  // 16-30 actors: Yellow
        31, "#ff8000",  // 31-50 actors: Orange
        51, "#ff0000"   // 50+ actors: Red
      ],
      fillOpacity: 0.6
    });
    
    // Add text labels for country names (one per country at centroid)
    const labelLayer = new atlas.layer.SymbolLayer(labelSource, IDS.polygonLayer + '_labels', {
      iconOptions: {
        image: 'none'  // Remove pin icons
      },
      textOptions: {
        textField: ['get', 'country'],
        size: 11,
        color: '#000000',
        haloColor: '#ffffff',
        haloWidth: 2,
        haloBlur: 1,
        font: ['SegoeUi-Bold'],
        offset: [0, 0],
        anchor: 'center'
      }
    });

    // Outline layer for country borders
    const outlineLayer = new atlas.layer.LineLayer(dataSource, IDS.outlineLayer, {
      strokeColor: "#ffffff",
      strokeWidth: 1.5,
      strokeOpacity: 0.8
    });

    map.layers.add(polygonLayer);
    map.layers.add(outlineLayer);
    map.layers.add(labelLayer);
    
    // Show the legend for country view
    const legend = document.getElementById("countryLegend");
    if (legend) legend.classList.remove("hidden");

    // Register mouse interactions (click to show details, hover for pointer cursor)
    if (onCountryClick) {
      // Delay ensures layers are fully registered before adding event listeners
      setTimeout(() => {
        // Handle clicks on countries to show threat actor details
        map.events.add("click", polygonLayer, (e) => {
          if (e.shapes && e.shapes.length > 0) {
            const props = e.shapes[0].getProperties();
            onCountryClick(props);
          }
        });

        // Change cursor to pointer when hovering over countries
        map.events.add("mousemove", polygonLayer, () => {
          map.getCanvasContainer().style.cursor = "pointer";
        });

        // Restore default cursor when leaving country areas
        map.events.add("mouseleave", polygonLayer, () => {
          map.getCanvasContainer().style.cursor = "grab";
        });
      }, 100);
    }
  } else {
    // Heatmap mode - use point features at country centroids for diffuse intensity visualization
    for (const [country, count] of counts.entries()) {
      const centroid = COUNTRY_CENTROIDS[country];
      if (!centroid) {
        console.warn(`No centroid defined for country: ${country}`);
        continue;
      }
      
      // Weight determines the intensity at this point
      const weight = Math.max(1, count * 2);
      dataSource.add(
        new atlas.data.Feature(new atlas.data.Point(centroid), {
          weight,
          country,
          count,
          actors: actorsByCountry.get(country)
        })
      );
    }

    // Create heatmap layer with intensity based on threat actor count
    const heat = new atlas.layer.HeatMapLayer(dataSource, IDS.heatLayer, {
      weight: [
        "interpolate",
        ["linear"],
        ["get", "weight"],
        1,   0.25,
        5,   0.45,
        10,  0.65,
        25,  0.95,
        50,  1.25,
        100, 1.60,
        200, 2.00
      ],
      radius: 45,
      intensity: 2,
      opacity: 0.85
    });

    map.layers.add(heat);
    
    // Add click handling for heatmap - find nearest country point
    if (onCountryClick) {
      setTimeout(() => {
        map.events.add("click", (e) => {
          // Get geographic position of click
          const clickPosition = e.position;
          let nearestFeature = null;
          let minDistance = Infinity;
          
          // Query all features from the data source
          const features = dataSource.toJson().features;
          
          for (const feature of features) {
            if (feature.geometry.type === "Point") {
              const [lon, lat] = feature.geometry.coordinates;
              
              // Convert both click and feature position to pixels for accurate distance
              const featurePixel = map.positionsToPixels([[lon, lat]])[0];
              const clickPixel = map.positionsToPixels([clickPosition])[0];
              
              // Calculate pixel distance
              const dx = featurePixel[0] - clickPixel[0];
              const dy = featurePixel[1] - clickPixel[1];
              const distance = Math.sqrt(dx * dx + dy * dy);
              
              // Find nearest point within heatmap radius (100px)
              if (distance < minDistance) {
                minDistance = distance;
                nearestFeature = feature;
              }
            }
          }
          
          // Show details if we clicked within reasonable range (150px to account for heatmap spread)
          if (nearestFeature && minDistance < 150) {
            onCountryClick(nearestFeature.properties);
          }
        });
        
        // Change cursor on hover over heatmap areas
        map.getCanvasContainer().style.cursor = "pointer";
      }, 100);
    }
  }
}


function disable(map) {
  // Remove layers first
  try {
    if (map.layers.getLayerById(IDS.polygonLayer + '_labels')) {
      map.layers.remove(IDS.polygonLayer + '_labels');
    }
  } catch (e) { /* ignore */ }
  
  try {
    const outlineLayer = map.layers.getLayerById(IDS.outlineLayer);
    if (outlineLayer) {
      map.events.remove('click', outlineLayer);
      map.events.remove('mousemove', outlineLayer);
      map.events.remove('mouseleave', outlineLayer);
      map.layers.remove(IDS.outlineLayer);
    }
  } catch (e) { /* ignore */ }
  
  try {
    const polygonLayer = map.layers.getLayerById(IDS.polygonLayer);
    if (polygonLayer) {
      map.events.remove('click', polygonLayer);
      map.events.remove('mousemove', polygonLayer);
      map.events.remove('mouseleave', polygonLayer);
      map.layers.remove(IDS.polygonLayer);
    }
  } catch (e) { /* ignore */ }
  
  try {
    if (map.layers.getLayerById(IDS.heatLayer)) {
      map.layers.remove(IDS.heatLayer);
    }
  } catch (e) { /* ignore */ }
  
  // Remove source after all layers are removed
  try {
    if (map.sources.getById(IDS.source)) {
      map.sources.remove(IDS.source);
    }
  } catch (e) { /* ignore */ }
  
  // Remove label source
  try {
    if (map.sources.getById(IDS.source + '_labels')) {
      map.sources.remove(IDS.source + '_labels');
    }
  } catch (e) { /* ignore */ }
  
  // Hide the legend
  const legend = document.getElementById("countryLegend");
  if (legend) legend.classList.add("hidden");
  
  map.getCanvasContainer().style.cursor = 'grab';
}
