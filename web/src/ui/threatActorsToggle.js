import { toggleThreatActorsHeatmap } from "../overlays/threatActorsHeatmap.js";

export function addThreatActorsToggle(map, onCountryClick) {
  const wrap = document.createElement("div");
  wrap.id = "threatActorsControlPanel";
  wrap.style.position = "fixed";
  wrap.style.top = "20px";
  wrap.style.left = "20px";
  wrap.style.zIndex = "5000";
  wrap.style.pointerEvents = "auto";
  wrap.style.display = "none";
  wrap.style.gap = "8px";
  wrap.style.background = "rgba(31, 41, 55, 0.95)";
  wrap.style.padding = "10px 12px";
  wrap.style.borderRadius = "8px";
  wrap.style.backdropFilter = "blur(10px)";
  wrap.style.boxShadow = "0 4px 12px rgba(0,0,0,0.3)";
  wrap.style.transition = "transform 0.3s ease, opacity 0.3s ease";

  wrap.innerHTML = `
    <label style="color:#fff;font-size:14px;font-weight:600;padding:0 8px;display:flex;align-items:center;">Threat Map</label>
    <button id="taToggle" style="padding:8px 14px;border-radius:6px;border:none;background:#3b82f6;color:#fff;cursor:pointer;font-size:13px;font-weight:600;">Off</button>
    <select id="taMode" style="padding:8px 10px;border-radius:6px;border:none;background:#374151;color:#fff;cursor:pointer;font-size:13px;" disabled>
      <option value="heatmap">Heatmap</option>
      <option value="country">Country View</option>
    </select>
    <button id="hideControlPanel" style="padding:8px 12px;border-radius:6px;border:none;background:#ef4444;color:#fff;cursor:pointer;font-size:16px;font-weight:600;margin-left:4px;">×</button>
  `;

  document.body.appendChild(wrap);
  
  // Create show button (visible by default)
  const showBtn = document.createElement("button");
  showBtn.id = "showControlPanel";
  showBtn.style.position = "fixed";
  showBtn.style.top = "20px";
  showBtn.style.left = "20px";
  showBtn.style.zIndex = "5000";
  showBtn.style.padding = "10px 14px";
  showBtn.style.borderRadius = "8px";
  showBtn.style.border = "none";
  showBtn.style.background = "#10b981";
  showBtn.style.color = "#fff";
  showBtn.style.cursor = "pointer";
  showBtn.style.fontSize = "14px";
  showBtn.style.fontWeight = "600";
  showBtn.style.boxShadow = "0 4px 12px rgba(0,0,0,0.3)";
  showBtn.style.display = "block";
  showBtn.textContent = "☰ Threat Map";

  document.body.appendChild(showBtn);

  let on = true;  // Start enabled by default
  let mode = "country";
  const toggleBtn = wrap.querySelector("#taToggle");
  const modeSelect = wrap.querySelector("#taMode");
  const hideBtn = wrap.querySelector("#hideControlPanel");
  
  // Set default mode to Country View
  modeSelect.value = "country";
  toggleBtn.textContent = "On";
  toggleBtn.style.background = "#10b981";
  modeSelect.disabled = false;
  
  // Hide/Show control panel handlers
  hideBtn.addEventListener("click", () => {
    wrap.style.opacity = "0";
    wrap.style.transform = "translateX(20px)";
    setTimeout(() => {
      wrap.style.display = "none";
      showBtn.style.display = "block";
    }, 300);
  });
  
  showBtn.addEventListener("click", () => {
    wrap.style.display = "flex";
    setTimeout(() => {
      wrap.style.opacity = "1";
      wrap.style.transform = "translateX(0)";
    }, 10);
    showBtn.style.display = "none";
  });

  async function applyVisualization() {
    toggleBtn.disabled = true;
    modeSelect.disabled = true;

    try {
      // Always turn off heatmap first
      await toggleThreatActorsHeatmap(map, false);

      if (on) {
        if (mode === "heatmap") {
          // Pass mode and onCountryClick to enable click handling in heatmap mode too
          await toggleThreatActorsHeatmap(map, true, "heatmap", onCountryClick);
        } else {
          // Country view - use polygon layer with click handler
          await toggleThreatActorsHeatmap(map, true, "country", onCountryClick);
        }
      }

      toggleBtn.textContent = on ? "On" : "Off";
      toggleBtn.style.background = on ? "#10b981" : "#3b82f6";
      modeSelect.disabled = !on;
    } catch (e) {
      console.error("Visualization toggle failed:", e);
      const msg = e?.message || String(e);
      if (msg) alert("Failed to toggle visualization: " + msg);
      on = false;
      toggleBtn.textContent = "Off";
      toggleBtn.style.background = "#3b82f6";
      modeSelect.disabled = true;
    } finally {
      toggleBtn.disabled = false;
      if (on) modeSelect.disabled = false;
    }
  }

  toggleBtn.addEventListener("click", async () => {
    on = !on;
    await applyVisualization();
  });

  modeSelect.addEventListener("change", async () => {
    mode = modeSelect.value;
    if (on) {
      await applyVisualization();
    }
  });
  
  // Load visualization immediately on initialization
  applyVisualization();
}
