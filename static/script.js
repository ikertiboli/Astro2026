const cameraStatusDot = document.getElementById("camera-status-dot");
const cameraStatusText = document.getElementById("camera-status-text");
const isoSelect = document.getElementById("iso-select");
const apertureSelect = document.getElementById("aperture-select");
const shutterSelect = document.getElementById("shutter-select");
const captureButton = document.getElementById("capture-btn");
const lastPhotoThumb = document.getElementById("last-photo-thumb");
const lastPhotoEmpty = document.getElementById("last-photo-empty");

function setCameraStatus(online, text) {
  cameraStatusDot.classList.remove("online", "offline");
  cameraStatusDot.classList.add(online ? "online" : "offline");
  cameraStatusText.textContent = text;
}

function fillSelect(selectElement, values) {
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
}

function setPreview(imageUrl) {
  if (imageUrl) {
    lastPhotoThumb.src = imageUrl;
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
    setCameraStatus(true, "Cámara conectada");
  } catch (error) {
    fillSelect(isoSelect, []);
    fillSelect(apertureSelect, []);
    fillSelect(shutterSelect, []);
    setCameraStatus(false, "Cámara no disponible");
  }
}

async function loadLastPhoto() {
  try {
    const response = await fetch("/api/last-photo");
    if (!response.ok) {
      throw new Error("No se pudo cargar la última foto");
    }

    const data = await response.json();
    const thumbnailUrl = data.thumbnail_url || data.thumbnail || data.image_url || "";
    setPreview(thumbnailUrl);
  } catch (error) {
    setPreview("");
  }
}

async function capture() {
  captureButton.disabled = true;
  setCameraStatus(true, "Capturando fotografía…");

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
    const thumbnailUrl =
      captureData.thumbnail_url || captureData.thumbnail || captureData.image_url || "";

    setPreview(thumbnailUrl);
    setCameraStatus(true, "Foto capturada correctamente");
  } catch (error) {
    setCameraStatus(false, "Error durante la captura");
  } finally {
    captureButton.disabled = false;
  }
}

captureButton.addEventListener("click", capture);

loadSettings();
loadLastPhoto();
