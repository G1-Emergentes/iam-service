"use strict";
(() => {
  const byId = id => document.getElementById(id);
  const maxBytes = 8 * 1024 * 1024;
  let photo = null, previewUrl = null, stream = null, heightCm = null, weightKg = null;
  let revision = 0, selecting = 0;
  const progress = ["TU FOTO", "TU ALTURA", "TU PESO", "CONFIRMA TUS DATOS"];

  function message(text, error = false) {
    byId("photo-status").textContent = text;
    byId("photo-status").dataset.state = error ? "error" : "info";
  }
  function stopCamera() {
    selecting++;
    if (stream) stream.getTracks().forEach(track => track.stop());
    stream = null;
    byId("camera").srcObject = null;
    byId("camera-panel").hidden = true;
    byId("open-camera").disabled = false;
  }
  function step(index) {
    stopCamera();
    for (let i = 0; i < 4; i++) byId("photo-step-" + i).hidden = i !== index;
    byId("photo-progress").textContent = `PASO ${index + 1} DE 4 · ${progress[index]}`;
    message("");
    const heading = byId("photo-step-" + index).querySelector("h2");
    heading.tabIndex = -1;
    heading.focus();
  }
  function mode(manual) {
    stopCamera();
    byId("manual-panel").hidden = !manual;
    byId("manual-viewer").hidden = !manual;
    byId("photo-flow").hidden = manual;
    byId("photo-preview-panel").hidden = manual;
    byId("manual-mode").setAttribute("aria-pressed", String(manual));
    byId("photo-mode").setAttribute("aria-pressed", String(!manual));
    window.dispatchEvent(new Event("resize"));
  }
  byId("manual-mode").addEventListener("click", () => mode(true));
  byId("photo-mode").addEventListener("click", () => mode(false));
  document.querySelectorAll("[data-back]").forEach(button => button.addEventListener("click", () => step(Number(button.dataset.back))));

  async function choosePhoto(file) {
    const current = ++revision;
    byId("photo-next").disabled = true;
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = null; photo = null;
    byId("photo-preview").hidden = true;
    byId("photo-preview").removeAttribute("src");
    byId("photo-placeholder").hidden = false;
    if (!file) return;
    byId("clear-photo").hidden = false;
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || file.size > maxBytes || file.size === 0) {
      message("Elige una foto JPEG, PNG o WebP de hasta 8 MB.", true); return;
    }
    try {
      const bitmap = await createImageBitmap(file);
      const valid = Math.min(bitmap.width, bitmap.height) >= 256 && bitmap.width * bitmap.height <= 20_000_000;
      bitmap.close();
      if (current !== revision) return;
      if (!valid) throw new Error("Usa una imagen de al menos 256 × 256 píxeles y hasta 20 megapíxeles.");
      photo = file;
      previewUrl = URL.createObjectURL(file);
      byId("photo-preview").src = previewUrl;
      byId("photo-preview").hidden = false;
      byId("photo-placeholder").hidden = true;
      byId("photo-next").disabled = false;
      message("Foto seleccionada. Comprueba que se vean tu cabeza y tus pies. Aún no se ha enviado.");
    } catch (error) {
      if (current === revision) message(error.message || "No se pudo abrir esa imagen. Elige otra foto.", true);
    }
  }
  byId("photo-file").addEventListener("change", event => { stopCamera(); choosePhoto(event.target.files[0]); });
  byId("photo-next").addEventListener("click", () => { if (photo) step(1); });
  byId("open-camera").addEventListener("click", async () => {
    if (!navigator.mediaDevices?.getUserMedia) { message("La cámara requiere HTTPS o localhost. Puedes cargar una foto.", true); return; }
    const current = ++selecting;
    byId("open-camera").disabled = true;
    try {
      const next = await navigator.mediaDevices.getUserMedia({video: {facingMode: {ideal: "environment"}}, audio: false});
      if (current !== selecting) { next.getTracks().forEach(track => track.stop()); return; }
      stream = next;
      byId("camera").srcObject = stream;
      byId("camera-panel").hidden = false;
      await byId("camera").play();
      message("Colócate de cuerpo completo antes de tomar la foto.");
    } catch (_) {
      stopCamera();
      message("No se pudo abrir la cámara. Revisa el permiso o carga una foto desde tu dispositivo.", true);
    }
  });
  byId("close-camera").addEventListener("click", stopCamera);
  byId("take-photo").addEventListener("click", async () => {
    const video = byId("camera");
    if (!video.videoWidth || !video.videoHeight) { message("Espera a que la cámara esté lista.", true); return; }
    const image = document.createElement("canvas");
    const scale = Math.min(1, 2560 / Math.max(video.videoWidth, video.videoHeight));
    image.width = Math.round(video.videoWidth * scale); image.height = Math.round(video.videoHeight * scale);
    image.getContext("2d").drawImage(video, 0, 0, image.width, image.height);
    const current = revision;
    const blob = await new Promise(resolve => image.toBlob(resolve, "image/jpeg", .9));
    stopCamera();
    if (current === revision && blob) {
      byId("photo-file").value = "";
      await choosePhoto(new File([blob], "capture.jpg", {type: "image/jpeg"}));
    }
  });
  window.addEventListener("pagehide", stopCamera);
  document.addEventListener("visibilitychange", () => { if (document.hidden) stopCamera(); });

  function configureUnit(input, unit, first, second) {
    const useSecond = unit.value === second.unit;
    input.min = useSecond ? second.min : first.min;
    input.max = useSecond ? second.max : first.max;
    input.step = useSecond ? second.step : first.step;
    input.value = "";
  }
  byId("height-unit").addEventListener("change", () => {
    heightCm = null;
    configureUnit(byId("declared-height"), byId("height-unit"), {min:130,max:220,step:.1}, {unit:"m",min:1.3,max:2.2,step:.001});
  });
  byId("weight-unit").addEventListener("change", () => {
    weightKg = null;
    configureUnit(byId("declared-weight"), byId("weight-unit"), {min:30,max:250,step:.1}, {unit:"lb",min:66.2,max:551.1,step:.1});
  });
  byId("photo-step-1").addEventListener("submit", event => {
    event.preventDefault();
    heightCm = Number(byId("declared-height").value) * (byId("height-unit").value === "m" ? 100 : 1);
    if (!Number.isFinite(heightCm) || heightCm < 130 || heightCm > 220) { message("Revisa la altura y su unidad.", true); return; }
    step(2);
  });
  byId("photo-step-2").addEventListener("submit", event => {
    event.preventDefault();
    weightKg = Number(byId("declared-weight").value) * (byId("weight-unit").value === "lb" ? .45359237 : 1);
    weightKg = Math.round(weightKg * 1000) / 1000;
    if (!Number.isFinite(weightKg) || weightKg < 30 || weightKg > 250) { message("Revisa el peso y su unidad.", true); return; }
    byId("height-summary").textContent = heightCm.toLocaleString("es-PE", {maximumFractionDigits:1}) + " cm";
    byId("weight-summary").textContent = weightKg.toLocaleString("es-PE", {maximumFractionDigits:1}) + " kg";
    step(3);
  });
  byId("submit-photo").addEventListener("click", async () => {
    if (!photo || heightCm === null || weightKg === null) { message("Completa la foto, altura y peso primero.", true); return; }
    const current = revision;
    const submit = byId("submit-photo"); submit.disabled = true;
    const data = new FormData(); data.append("photo", photo); data.append("height_cm", heightCm); data.append("weight_kg", weightKg);
    message("Validando tu foto y tus datos en esta PC…");
    try {
      const response = await fetch("/api/estimations", {method:"POST",body:data,cache:"no-store"});
      const result = await response.json();
      if (current !== revision) return;
      if (response.status === 503 && result.error === "sam_access_pending") {
        message("Estimación por foto pendiente de habilitación. No se calcularon medidas ni se guardó tu foto. Puedes continuar con medidas manuales.");
      } else if (!response.ok) {
        message(response.status === 413 ? "La foto supera los 8 MB. Elige una más pequeña." : "No se pudo validar la foto o tus datos. Revisa el formato, tamaño y unidades.", true);
      } else {
        message("El resultado del estimador requiere revisión antes de generar un avatar. Esta versión aún no permite aplicarlo.");
      }
    } catch (_) { if (current === revision) message("No se pudo conectar con el worker. Intenta de nuevo.", true); }
    finally { submit.disabled = false; }
  });
  byId("use-manual").addEventListener("click", () => {
    if (heightCm === null) return;
    const form = byId("measurements");
    for (const input of form.querySelectorAll("input")) input.value = input.name === "height" ? heightCm : "";
    byId("result").hidden = true;
    byId("status").textContent = "Conservamos tu altura declarada. Introduce las otras cuatro medidas; no se han estimado desde tu foto.";
    mode(true);
    form.querySelector('[name="shoulderWidth"]').focus();
  });
  byId("clear-photo").addEventListener("click", () => {
    revision++; stopCamera();
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = null; photo = null; heightCm = null; weightKg = null;
    byId("photo-preview").removeAttribute("src"); byId("photo-preview").hidden = true;
    byId("photo-placeholder").hidden = false;
    byId("photo-file").value = "";
    byId("photo-step-1").reset(); byId("photo-step-2").reset();
    byId("declared-height").min = 130; byId("declared-height").max = 220; byId("declared-height").step = .1;
    byId("declared-weight").min = 30; byId("declared-weight").max = 250; byId("declared-weight").step = .1;
    byId("photo-next").disabled = true; byId("clear-photo").hidden = true;
    step(0);
    message("Foto y datos descartados de esta página.");
  });
})();
