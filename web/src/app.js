import { createMap } from "./map/map-init.js";
import { addThreatActorsToggle } from "./ui/threatActorsToggle.js";
import { showCountryDetails, initPanelControls } from "./ui/panelManager.js";
import { addAutoScrollControl } from "./ui/autoScroll.js";

async function main() {
  console.log("Starting Sentinel Activity Maps...");

  const map = await createMap({
    containerId: "map",
    initialView: { center: [-20, 25], zoom: 2 },
    style: "road"
  });

  map.events.add("ready", () => {
    console.log("Map ready.");
    
    initPanelControls();
    addThreatActorsToggle(map, (countryProps) => {
      showCountryDetails(countryProps);
    });
    addAutoScrollControl(map);
  });

  map.events.add("error", (e) => {
    console.error("Map error:", e);
  });
}

main().catch((e) => {
  console.error("Startup failed:", e?.message || String(e));
});
