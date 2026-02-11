/* global atlas */

/**
 * Threat Intel Indicators Overlay
 * Displays threat intelligence indicators from pre-generated GeoJSON
 */

const THREAT_INTEL_SOURCE_ID = "threat-intel-source";
const THREAT_INTEL_LAYER_ID = "threat-intel-layer";

let isEnabled = false;

/**
 * Toggle the threat intel overlay on or off
 */
export async function toggleThreatIntelOverlay(map, turnOn) {
  if (turnOn) {
    await enable(map);
  } else {
    disable(map);
  }
}

/**
 * Enable the overlay - fetch and display GeoJSON from blob storage
 */
async function enable(map) {
  if (isEnabled) return;

  try {
    console.log("Loading threat intel indicators from API...");

    // Fetch GeoJSON from blob storage via API proxy
    const response = await fetch("/api/data/threat-intel");
    if (!response.ok) {
      throw new Error(`Failed to load threat intel: ${response.status} ${response.statusText}`);
    }

    const geojson = await response.json();
    
    if (!geojson.features || geojson.features.length === 0) {
      console.warn("No threat intel indicators found");
      throw new Error("No threat intelligence indicators available");
    }

    console.log(`Loaded ${geojson.features.length} threat intel indicators`);

    // Create data source
    const dataSource = new atlas.source.DataSource(THREAT_INTEL_SOURCE_ID);
    map.sources.add(dataSource);
    dataSource.add(geojson);

    // Find max for color scaling
    const counts = geojson.features
      .map(f => f.properties?.count || f.properties?.Count || 1)
      .filter(c => typeof c === 'number' && !isNaN(c));
    const maxCount = counts.length > 0 ? Math.max(...counts) : 1;

    console.log(`Threat intel count range: 1 to ${maxCount}`);

    // Add bubble layer for indicators
    const bubbleLayer = new atlas.layer.BubbleLayer(dataSource, THREAT_INTEL_LAYER_ID, {
      radius: [
        "interpolate",
        ["linear"],
        ["coalesce", ["get", "count"], ["get", "Count"], 1],
        1, 5,
        Math.max(maxCount / 2, 1), 15,
        maxCount, 25
      ],
      color: [
        "interpolate",
        ["linear"],
        ["coalesce", ["get", "count"], ["get", "Count"], 1],
        1, "#ff6b6b",
        Math.max(maxCount / 2, 1), "#ff0000",
        maxCount, "#8b0000"
      ],
      strokeColor: "#ffffff",
      strokeWidth: 1,
      opacity: 0.7,
      blur: 0.5
    });

    map.layers.add(bubbleLayer);

    // Create popup for hover interactions
    const popup = new atlas.Popup({
      pixelOffset: [0, -10],
      closeButton: false
    });

    // Show details on hover
    map.events.add("mousemove", bubbleLayer, (e) => {
      if (e.shapes && e.shapes.length > 0) {
        const props = e.shapes[0].getProperties();
        
        let content = '<div style="padding:10px;max-width:250px;">';
        
        // Show available properties
        if (props.ObservableValue || props.ip) {
          content += `<strong>IP:</strong> ${props.ObservableValue || props.ip}<br/>`;
        }
        
        if (props.Type || props.type) {
          content += `<strong>Type:</strong> ${props.Type || props.type}<br/>`;
        }
        
        if (props.count || props.Count) {
          content += `<strong>Count:</strong> ${props.count || props.Count}<br/>`;
        }
        
        if (props.Confidence || props.confidence) {
          content += `<strong>Confidence:</strong> ${props.Confidence || props.confidence}<br/>`;
        }
        
        if (props.Description || props.description) {
          const desc = props.Description || props.description;
          const truncated = desc.length > 100 ? desc.substring(0, 100) + "..." : desc;
          content += `<div style="margin-top:4px;font-size:11px;color:#666;">${truncated}</div>`;
        }
        
        content += '</div>';
        
        popup.setOptions({
          content: content,
          position: e.shapes[0].getCoordinates()
        });
        popup.open(map);
      }
    });

    map.events.add("mouseleave", bubbleLayer, () => {
      popup.close();
    });

    // Change cursor on hover
    map.events.add("mousemove", bubbleLayer, () => {
      map.getCanvasContainer().style.cursor = "pointer";
    });

    map.events.add("mouseleave", bubbleLayer, () => {
      map.getCanvasContainer().style.cursor = "grab";
    });

    isEnabled = true;
    console.log("Threat intel overlay enabled");

  } catch (error) {
    console.error("Error enabling threat intel overlay:", error);
    disable(map);
    throw error;
  }
}

/**
 * Disable the overlay - remove layers and sources
 */
function disable(map) {
  // Remove layer
  try {
    const layer = map.layers.getLayerById(THREAT_INTEL_LAYER_ID);
    if (layer) {
      map.events.remove("mousemove", layer);
      map.events.remove("mouseleave", layer);
      map.layers.remove(THREAT_INTEL_LAYER_ID);
    }
  } catch (e) {
    console.warn("Error removing threat intel layer:", e);
  }

  // Remove source
  try {
    if (map.sources.getById(THREAT_INTEL_SOURCE_ID)) {
      map.sources.remove(THREAT_INTEL_SOURCE_ID);
    }
  } catch (e) {
    console.warn("Error removing threat intel source:", e);
  }

  map.getCanvasContainer().style.cursor = "grab";
  isEnabled = false;
  console.log("Threat intel overlay disabled");
}
