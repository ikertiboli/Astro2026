const cameraStatusDot = document.getElementById("camera-status-dot");
const cameraStatusText = document.getElementById("camera-status-text");
const isoSelect = document.getElementById("iso-select");
const apertureSelect = document.getElementById("aperture-select");
const shutterSelect = document.getElementById("shutter-select");
const captureButton = document.getElementById("capture-btn");
const lastPhotoThumb = document.getElementById("last-photo-thumb");
const lastPhotoEmpty = document.getElementById("last-photo-empty");
const AUTO_REFRESH_MS = 10000;
let isCaptureInProgress = false;
let isAutoRefreshing = false;
let autoRefreshIntervalId = null;

function setCameraStatus(status, text) {
  cameraStatusDot.classList.remove("online", "offline", "warning");
  cameraStatusDot.classList.add(status);
  cameraStatusText.textContent = text;
}

function fillSelect(selectElement, values) {
  const previousValue = selectElement.value;
  selectElement.innerHTML = "";

  if (!Array.isArray(values) || values.length === 0) {
    const emptyOption = document.createElement("option");
    emptyOption.value = "";
    emptyOption.textContent = "No disponible";
    selectElement.appendChild(emptyOption);
    return;
  }

  values.forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    selectElement.appendChild(option);
  });

  if (values.includes(previousValue)) {
    selectElement.value = previousValue;
  }
}

function withCacheBuster(url) {
  const separator = url.includes("?") ? "&" : "?";
  return `${url}${separator}t=${Date.now()}`;
}

function setPreview(imageUrl, forceFresh = false) {
  if (imageUrl) {
    lastPhotoThumb.src = forceFresh ? withCacheBuster(imageUrl) : imageUrl;
    lastPhotoThumb.hidden = false;
    lastPhotoEmpty.hidden = true;
    return;
  }

  lastPhotoThumb.src = "";
  lastPhotoThumb.hidden = true;
  lastPhotoEmpty.hidden = false;
}

async function loadSettings() {
  try {
    const response = await fetch("/api/settings");
    if (!response.ok) {
      throw new Error("No se pudieron cargar ajustes");
    }

    const settings = await response.json();

    fillSelect(isoSelect, settings.iso);
    fillSelect(apertureSelect, settings.apertures);
    fillSelect(shutterSelect, settings.shutter_speeds);
    setCameraStatus("online", "Cámara conectada");
  } catch (error) {
    fillSelect(isoSelect, []);
    fillSelect(apertureSelect, []);
    fillSelect(shutterSelect, []);
    setCameraStatus("offline", "Cámara no disponible");
  }
}

async function loadLastPhoto(forceFresh = false) {
  try {
    const response = await fetch("/api/last-photo");
    if (!response.ok) {
      throw new Error("No se pudo cargar la última foto");
    }

    const data = await response.json();
    setPreview(data.thumbnail_url || "", forceFresh);
  } catch (error) {
    setPreview("");
  }
}

async function runAutoRefresh() {
  if (isCaptureInProgress || isAutoRefreshing || document.hidden) {
    return;
  }

  isAutoRefreshing = true;
  try {
    await Promise.allSettled([loadSettings(), loadLastPhoto(true)]);
  } finally {
    isAutoRefreshing = false;
  }
}

function startAutoRefresh() {
  if (autoRefreshIntervalId !== null) {
    return;
  }

  autoRefreshIntervalId = window.setInterval(runAutoRefresh, AUTO_REFRESH_MS);
}

async function capture() {
  isCaptureInProgress = true;
  captureButton.disabled = true;
  setCameraStatus("online", "Capturando fotografía…");

  try {
    const payload = {
      iso: isoSelect.value,
      aperture: apertureSelect.value,
      shutter_speed: shutterSelect.value,
    };

    const paramsResponse = await fetch("/api/set-params", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!paramsResponse.ok) {
      throw new Error("No se pudieron aplicar parámetros");
    }

    const captureResponse = await fetch("/api/capture", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });

    if (!captureResponse.ok) {
      throw new Error("Error al capturar fotografía");
    }

    const captureData = await captureResponse.json();
    setPreview(captureData.thumbnail_url || "", true);
    setCameraStatus("online", "Foto capturada correctamente");
  } catch (error) {
    setCameraStatus("warning", "Error durante la captura");
  } finally {
    isCaptureInProgress = false;
    captureButton.disabled = false;
  }
}

captureButton.addEventListener("click", capture);
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) {
    runAutoRefresh();
  }
});

Promise.allSettled([loadSettings(), loadLastPhoto(true)]).then(startAutoRefresh);
