import { createMap } from "./map/map-init.js";
import { addThreatActorsToggle } from "./ui/threatActorsToggle.js";
import { addThreatIntelToggle } from "./ui/threatIntelToggle.js";
import { showCountryDetails, initPanelControls } from "./ui/panelManager.js";
import { addAutoScrollControl } from "./ui/autoScroll.js";

const debugEl = document.getElementById("debug");
const overlayEl = document.getElementById("loadingOverlay");

function debug(msg) {
  if (!debugEl) return;
  debugEl.textContent = msg + "\n" + debugEl.textContent;
}

function hideLoading() {
  if (overlayEl) overlayEl.classList.add("hidden");
}

async function main() {
  debug("Starting…");

  const map = await createMap({
    containerId: "map",
    initialView: { center: [-20, 25], zoom: 2 },
    style: "road"
  });

  map.events.add("ready", () => {
    debug("Map ready.");
    hideLoading();
    
    initPanelControls();
    addThreatActorsToggle(map, (countryProps) => {
      showCountryDetails(countryProps);
    });
    addThreatIntelToggle(map);
    addAutoScrollControl(map);
  });

  map.events.add("error", (e) => {
    debug("Map error: " + JSON.stringify(e));
  });
}

main().catch((e) => {
  debug("Startup failed: " + (e?.message || String(e)));
});
