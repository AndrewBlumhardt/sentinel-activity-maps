/* global atlas */

/**
 * Fetch Azure Maps configuration from the SWA Functions endpoint.
 */
async function getMapsConfig() {
  const resp = await fetch("/api/config", { cache: "no-store" });
  if (!resp.ok) throw new Error("Failed to load /api/config: " + resp.status);
  const data = await resp.json();
  // Adapt to current API response format {azureMapsKey: "..."}
  return {
    subscriptionKey: data.azureMapsKey
  };
}

function addMapControls(map) {
  map.controls.add(
    [
      new atlas.control.ZoomControl(),
      new atlas.control.PitchControl()
    ],
    { position: "bottom-right" }
  );

  map.controls.add(new atlas.control.CompassControl(), { position: "bottom-left" });

  map.controls.add(
    new atlas.control.FullscreenControl({ hideIfUnsupported: true }),
    { position: "top-right" }
  );

  // Style picker
  map.controls.add(
    new atlas.control.StyleControl({
      mapStyles: [
        "road",
        "grayscale_light",
        "grayscale_dark",
        "night",
        "road_shaded_relief",
        "satellite",
        "satellite_road_labels"
      ]
    }),
    { position: "top-right" }
  );
}

export async function createMap({ containerId, initialView, style }) {
  const cfg = await getMapsConfig();

  const map = new atlas.Map(containerId, {
    center: (initialView && initialView.center) || [-20, 25],
    zoom: (initialView && initialView.zoom) || 2,
    pitch: (initialView && initialView.pitch) || 0,
    bearing: (initialView && initialView.bearing) || 0,
    language: "en-US",
    view: "Auto",
    style: style || "road",
    authOptions: {
      authType: "subscriptionKey",
      subscriptionKey: cfg.subscriptionKey
    }
  });

  addMapControls(map);
  return map;
}
