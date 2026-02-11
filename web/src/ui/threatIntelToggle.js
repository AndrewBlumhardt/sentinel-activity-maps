import { toggleThreatIntelOverlay } from "../overlays/threatIntelOverlay.js";

export function addThreatIntelToggle(map) {
  const wrap = document.createElement("div");
  wrap.id = "threatIntelControlPanel";
  wrap.style.position = "fixed";
  wrap.style.top = "80px";
  wrap.style.left = "20px";
  wrap.style.zIndex = "5000";
  wrap.style.pointerEvents = "auto";
  wrap.style.background = "rgba(31, 41, 55, 0.95)";
  wrap.style.padding = "10px 12px";
  wrap.style.borderRadius = "8px";
  wrap.style.backdropFilter = "blur(10px)";
  wrap.style.boxShadow = "0 4px 12px rgba(0,0,0,0.3)";
  wrap.style.display = "flex";
  wrap.style.alignItems = "center";
  wrap.style.gap = "8px";

  wrap.innerHTML = `
    <label style="color:#fff;font-size:14px;font-weight:600;">Threat Intel IPs</label>
    <button id="tiToggle" style="padding:8px 14px;border-radius:6px;border:none;background:#3b82f6;color:#fff;cursor:pointer;font-size:13px;font-weight:600;">Off</button>
  `;

  document.body.appendChild(wrap);

  let on = false;
  const toggleBtn = wrap.querySelector("#tiToggle");
  
  console.log("Threat Intel toggle initialized:", toggleBtn ? "button found" : "button NOT found");

  async function applyVisualization() {
    console.log("applyVisualization called, on =", on);
    toggleBtn.disabled = true;

    try {
      await toggleThreatIntelOverlay(map, on);
      toggleBtn.textContent = on ? "On" : "Off";
      toggleBtn.style.background = on ? "#10b981" : "#3b82f6";
      console.log("Threat intel visualization applied successfully");
    } catch (e) {
      console.error("Threat intel toggle failed:", e);
      const msg = e?.message || String(e);
      if (msg) alert("Failed to toggle threat intel: " + msg);
      on = false;
      toggleBtn.textContent = "Off";
      toggleBtn.style.background = "#3b82f6";
    } finally {
      toggleBtn.disabled = false;
    }
  }

  toggleBtn.addEventListener("click", async () => {
    console.log("Threat intel button clicked!");
    on = !on;
    await applyVisualization();
  });
}
