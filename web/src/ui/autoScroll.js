// Constants for auto-scroll behavior
const AUTO_SCROLL_SPEED = 0.1; // Degrees per frame
const AUTO_SCROLL_DIRECTION = "right"; // "left" or "right"
const MAX_LONGITUDE = 180;
const MIN_LONGITUDE = -180;

export function addAutoScrollControl(map) {
  let scrolling = false;
  let animationFrameId = null;

  const control = document.createElement("div");
  control.className = "azure-maps-control-container";
  control.style.position = "fixed";
  control.style.bottom = "160px";
  control.style.left = "10px";
  control.style.zIndex = "1000";
  control.style.pointerEvents = "auto";

  const button = document.createElement("button");
  button.className = "azure-maps-control-button";
  button.title = "Toggle Auto Scroll";
  button.textContent = "⇄";
  button.style.fontSize = "20px";
  button.style.width = "32px";
  button.style.height = "32px";
  button.style.padding = "0";
  button.style.border = "2px solid rgba(255, 255, 255, 0.5)";
  button.style.borderRadius = "4px";
  button.style.backgroundColor = "rgba(255, 255, 255, 0.9)";
  button.style.color = "#333";
  button.style.cursor = "pointer";
  button.style.transition = "all 0.2s";

  button.addEventListener("mouseenter", () => {
    button.style.backgroundColor = "rgba(255, 255, 255, 1)";
    button.style.borderColor = "rgba(0, 123, 255, 0.8)";
  });

  button.addEventListener("mouseleave", () => {
    if (!scrolling) {
      button.style.backgroundColor = "rgba(255, 255, 255, 0.9)";
      button.style.borderColor = "rgba(255, 255, 255, 0.5)";
    }
  });

  function scroll() {
    if (!scrolling) return;

    const camera = map.getCamera();
    let newCenter = [...camera.center];

    if (AUTO_SCROLL_DIRECTION === "right") {
      newCenter[0] += AUTO_SCROLL_SPEED;
      if (newCenter[0] > MAX_LONGITUDE) {
        newCenter[0] = MIN_LONGITUDE;
      }
    } else {
      newCenter[0] -= AUTO_SCROLL_SPEED;
      if (newCenter[0] < MIN_LONGITUDE) {
        newCenter[0] = MAX_LONGITUDE;
      }
    }

    map.setCamera({
      center: newCenter,
      type: "ease",
      duration: 50,
    });

    animationFrameId = requestAnimationFrame(scroll);
  }

  button.addEventListener("click", () => {
    scrolling = !scrolling;

    if (scrolling) {
      button.style.backgroundColor = "rgba(0, 123, 255, 0.9)";
      button.style.color = "#fff";
      button.style.borderColor = "rgba(0, 123, 255, 1)";
      scroll();
    } else {
      button.style.backgroundColor = "rgba(255, 255, 255, 0.9)";
      button.style.color = "#333";
      button.style.borderColor = "rgba(255, 255, 255, 0.5)";
      if (animationFrameId) {
        cancelAnimationFrame(animationFrameId);
        animationFrameId = null;
      }
    }
  });

  control.appendChild(button);
  document.body.appendChild(control);

  return control;
}
