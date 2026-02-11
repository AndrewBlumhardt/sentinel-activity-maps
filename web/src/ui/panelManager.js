/* global */

/**
 * Populate the left panel with country threat actor details
 */
export function showCountryDetails(countryProps) {
  const panel = document.getElementById("leftPanel");
  const titleEl = document.getElementById("panelTitle");
  const metaEl = document.getElementById("panelMeta");
  const listEl = document.getElementById("panelList");

  if (!panel || !titleEl || !metaEl || !listEl) {
    console.warn("Panel elements not found");
    return;
  }

  const { country, count, actors } = countryProps;

  // Update panel content section
  titleEl.textContent = country || "Unknown Country";
  
  metaEl.innerHTML = `
    <div style="margin-bottom: 16px;">
      <strong>${count}</strong> threat actor${count !== 1 ? "s" : ""} identified
    </div>
  `;

  // Build actor list
  if (actors && actors.length > 0) {
    const actorItems = actors.map(actor => {
      const name = actor.Name || "Unknown";
      const motivation = actor.Motivation || "Unknown";
      const source = actor.Source || "";
      const otherNames = actor["Other names"] || "";

      return `
        <div style="padding: 12px; border-bottom: 1px solid rgba(255,255,255,0.1);">
          <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 8px;">
            <div style="flex: 1;">
              <div style="font-weight: 600; margin-bottom: 4px;">${escapeHtml(name)}</div>
              <div style="font-size: 13px; color: rgba(255,255,255,0.7); margin-bottom: 4px;">
                <span style="display: inline-block; padding: 2px 8px; background: rgba(59, 130, 246, 0.2); border-radius: 4px; font-size: 11px;">
                  ${escapeHtml(motivation)}
                </span>
              </div>
            </div>
            <div style="display: flex; gap: 6px; margin-left: 8px;">
              <button class="actor-search-btn" data-name="${escapeHtml(name)}" data-aka="${escapeHtml(otherNames)}" style="padding: 6px 10px; background: #0078d4; border: none; border-radius: 4px; color: #fff; cursor: pointer; font-size: 11px; font-weight: 600; white-space: nowrap;" title="Search Bing">🔍 Search</button>
              <button class="actor-ai-btn" data-name="${escapeHtml(name)}" data-motivation="${escapeHtml(motivation)}" data-aka="${escapeHtml(otherNames)}" style="padding: 6px 10px; background: #10b981; border: none; border-radius: 4px; color: #fff; cursor: pointer; font-size: 11px; font-weight: 600; white-space: nowrap;" title="Generate AI Prompt">AI Prompt</button>
            </div>
          </div>
          ${otherNames ? `<div style="font-size: 12px; color: rgba(255,255,255,0.5);">aka: ${escapeHtml(otherNames)}</div>` : ""}
          ${source ? `<div style="font-size: 11px; color: rgba(255,255,255,0.4); margin-top: 4px;">Source: ${escapeHtml(source)}</div>` : ""}
        </div>
      `;
    }).join("");

    listEl.innerHTML = actorItems;
    
    // Wire up search buttons
    document.querySelectorAll(".actor-search-btn").forEach(btn => {
      btn.addEventListener("click", (e) => {
        const name = e.target.getAttribute("data-name");
        const aka = e.target.getAttribute("data-aka");
        const searchTerms = aka ? `${name} ${aka} threat actor` : `${name} threat actor`;
        const query = encodeURIComponent(searchTerms);
        window.open(`https://www.bing.com/search?q=${query}`, "_blank");
      });
    });
    
    // Wire up AI prompt buttons
    document.querySelectorAll(".actor-ai-btn").forEach(btn => {
      btn.addEventListener("click", (e) => {
        const name = e.target.getAttribute("data-name");
        const motivation = e.target.getAttribute("data-motivation");
        const aka = e.target.getAttribute("data-aka");
        
        const prompt = `Provide a comprehensive threat intelligence briefing on the ${name} cyber threat actor group${aka ? ` (also known as: ${aka})` : ""}. Include:

1. Overview and attribution
2. Primary motivations: ${motivation}
3. Known tactics, techniques, and procedures (TTPs)
4. MITRE ATT&CK framework mappings
5. Target sectors and geographies
6. Notable campaigns and incidents
7. Indicators of compromise (IOCs) if known
8. Recommended defensive measures

Please provide detailed, actionable intelligence suitable for security operations teams.`;
        
        // Copy to clipboard and optionally open ChatGPT
        navigator.clipboard.writeText(prompt).then(() => {
          const openChatGPT = confirm("AI prompt copied to clipboard!\n\nWould you like to open ChatGPT now?\n(You can paste the prompt there)");
          if (openChatGPT) {
            window.open("https://chat.openai.com/", "_blank");
          }
        }).catch(() => {
          // Fallback: show prompt in alert
          alert("Copy this prompt:\n\n" + prompt);
        });
      });
    });
  } else {
    listEl.innerHTML = `<div style="padding: 12px; color: rgba(255,255,255,0.5);">No actors found</div>`;
  }

  // Show panel
  panel.classList.remove("hidden");
  panel.setAttribute("aria-hidden", "false");
  
  // Hide floating threat map button since panel has its own button
  const floatingThreatBtn = document.getElementById("showControlPanel");
  if (floatingThreatBtn) {
    floatingThreatBtn.style.display = "none";
  }
}

/**
 * Hide the left panel
 */
export function hidePanel() {
  const panel = document.getElementById("leftPanel");
  if (panel) {
    // Move focus to a safe element before hiding to prevent aria-hidden accessibility warning
    const hideBtn = document.getElementById("panelHideBtn");
    if (hideBtn && document.activeElement === hideBtn) {
      // Move focus to the map container or body
      const mapContainer = document.getElementById("map");
      if (mapContainer) {
        mapContainer.focus();
      } else {
        document.body.focus();
      }
    }
    
    panel.classList.add("hidden");
    panel.setAttribute("aria-hidden", "true");
  }
  
  // Show floating threat map button when panel is hidden
  const floatingThreatBtn = document.getElementById("showControlPanel");
  const threatControl = document.getElementById("threatActorsControlPanel");
  if (floatingThreatBtn && (!threatControl || threatControl.style.display === "none")) {
    floatingThreatBtn.style.display = "block";
  }
}

/**
 * Initialize panel hide buttons
 */
export function initPanelControls() {
  const hideBtn = document.getElementById("panelHideBtn");
  const showThreatBtn = document.getElementById("showThreatMapBtn");
  
  // Close button in panel header
  if (hideBtn) {
    hideBtn.addEventListener("click", hidePanel);
  }
  
  // Show threat map control button
  if (showThreatBtn) {
    showThreatBtn.addEventListener("click", () => {
      const threatControl = document.getElementById("showControlPanel");
      if (threatControl) {
        threatControl.click();
      }
    });
  }
}

/**
 * Simple HTML escape to prevent XSS
 */
function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}
