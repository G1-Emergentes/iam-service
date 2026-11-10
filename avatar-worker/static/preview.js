"use strict";
const canvas = document.getElementById("avatar");
const status = document.getElementById("status");
const button = document.getElementById("generate");
const names = {height: "Altura", shoulderWidth: "Hombros", chest: "Pecho", waist: "Cintura", hip: "Cadera"};
const engine = new BABYLON.Engine(canvas, true);
const scene = new BABYLON.Scene(engine);
scene.clearColor = BABYLON.Color4.FromHexString("#E5DAF4FF");
const camera = new BABYLON.ArcRotateCamera("camera", Math.PI / 2, Math.PI / 2.1, 3.2, new BABYLON.Vector3(0, .9, 0), scene);
camera.attachControl(canvas, true);
camera.lowerRadiusLimit = 1;
camera.upperRadiusLimit = 6;
camera.wheelPrecision = 55;
camera.minZ = .01;
const light = new BABYLON.HemisphericLight("sky", new BABYLON.Vector3(0, 1, -1), scene);
light.intensity = 1.2;
const fill = new BABYLON.HemisphericLight("fill", new BABYLON.Vector3(0, 0, 1), scene);
fill.intensity = .5;
let container;
engine.runRenderLoop(() => scene.render());
window.addEventListener("resize", () => engine.resize());
function front() { camera.alpha = Math.PI / 2; camera.beta = Math.PI / 2.1; camera.radius = 3.2; camera.target.set(0, .9, 0); }
document.getElementById("front").addEventListener("click", front);

async function json(url, options) {
  const response = await fetch(url, {cache: "no-store", ...options});
  const body = await response.json();
  if (!response.ok) throw new Error(response.status === 429 ? "El worker está ocupado. Espera a que termine y vuelve a intentarlo." : "No se pudo procesar la solicitud. Revisa las medidas.");
  return body;
}

document.getElementById("measurements").addEventListener("submit", async event => {
  event.preventDefault();
  button.disabled = true;
  status.dataset.state = "info";
  status.textContent = "Preparando tu avatar… La primera carga del modelo puede tardar unos minutos.";
  try {
    const measurements = Object.fromEntries([...new FormData(event.target)].map(([k, v]) => [k, Number(v)]));
    const job = await json("/api/jobs", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(measurements)});
    let result;
    const deadline = Date.now() + 15 * 60 * 1000;
    while (Date.now() < deadline) {
      result = await json("/api/jobs/" + job.id);
      if (result.status === "succeeded") break;
      if (result.status === "failed") throw new Error("La generación falló. Puedes volver a intentarlo; revisa el registro del worker si persiste.");
      await new Promise(resolve => setTimeout(resolve, 1500));
    }
    if (result.status !== "succeeded") throw new Error("El trabajo sigue en proceso. Consulta su estado en la documentación del worker.");
    const next = await BABYLON.SceneLoader.LoadAssetContainerAsync("", result.modelUrl, scene, undefined, ".glb");
    if (container) container.dispose();
    container = next;
    container.addAllToScene();
    front();
    document.getElementById("empty").hidden = true;
    document.getElementById("values").replaceChildren(...Object.entries(names).map(([key, label]) => {
      const row = document.createElement("tr");
      for (const text of [label, result.result.requested[key] + " cm", result.result.achieved[key] + " cm"]) {
        const cell = document.createElement("td"); cell.textContent = text; row.appendChild(cell);
      }
      return row;
    }));
    document.getElementById("warning").textContent = result.result.warning;
    document.getElementById("download").href = result.modelUrl;
    document.getElementById("result").hidden = false;
    status.textContent = result.result.withinTolerance ? "Tu avatar está listo. Recuerda que es una aproximación visual." : "Avatar generado. Algunas medidas no alcanzaron el ajuste solicitado; revisa la comparación.";
  } catch (error) {
    status.dataset.state = "error";
    status.textContent = error.message;
  } finally { button.disabled = false; }
});
