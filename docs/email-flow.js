"use strict";
let flow = document.body.dataset.flow;
const linkParameters = new URLSearchParams(window.location.hash.slice(1));
const linkToken = linkParameters.get("access_token");
const linkType = linkParameters.get("type");
if (window.location.hash) history.replaceState(null, "", window.location.pathname);
const emailInput = document.getElementById("email");
const codeInput = document.getElementById("code");
const passwordInput = document.getElementById("password");
const status = document.getElementById("status");
const sendButton = document.getElementById("send-code");
const submitButton = document.getElementById("submit");
let verifiedSession = null;
const messages = {
  auth_request_rejected: "El código o los datos no son válidos. Si el código caducó, solicita uno nuevo.",
  too_many_attempts: "Se alcanzó el límite de solicitudes. Espera antes de volver a intentarlo.",
  session_revoked: "La sesión ya no está activa. Solicita un código nuevo.",
  password_changed_session_revocation_failed: "La contraseña cambió, pero no se pudo confirmar el cierre de todas las sesiones. Inicia sesión con la nueva contraseña.",
  invalid_password: "Revisa la nueva contraseña.",
  profile_initialization_failed: "No se pudo preparar el perfil. Intenta iniciar sesión de nuevo.",
};
async function post(path, body, token, method = "POST") {
  const headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = "Bearer " + token;
  const response = await fetch("/api/v1/auth/" + path, {
    method, headers, body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store", credentials: "omit"
  });
  const value = await response.json();
  if (!response.ok) {
    const error = new Error(messages[value.error] || "No se pudo completar la solicitud. Revisa los datos o inténtalo más tarde.");
    error.code = value.error;
    throw error;
  }
  return value;
}
function showStatus(message, state = "info") {
  status.textContent = message;
  status.dataset.state = state;
}

function busy(value) { sendButton.disabled = value; submitButton.disabled = value; }
emailInput.addEventListener("input", () => { verifiedSession = null; });
codeInput.addEventListener("input", () => { verifiedSession = null; });
sendButton.addEventListener("click", async () => {
  if (!emailInput.reportValidity()) return;
  busy(true); showStatus("Solicitando correo…");
  try {
    await post(flow === "recovery" ? "forgot-password" : "resend-verification", { email: emailInput.value });
    verifiedSession = null;
    showStatus(flow === "recovery"
      ? "Si la cuenta existe, recibirás un correo con un enlace. Revisa también Spam."
      : "Si la cuenta espera confirmación, recibirás un correo con un enlace. Revisa también Spam.", "success");
  } catch (error) { showStatus(error.message, "error"); }
  finally { busy(false); }
});
document.getElementById("email-form").addEventListener("submit", async (event) => {
  event.preventDefault(); busy(true); showStatus(verifiedSession ? "Actualizando contraseña…" : "Verificando código…");
  try {
    if (!verifiedSession) verifiedSession = await post("verify-email", {
      email: emailInput.value, token: codeInput.value.trim(), type: flow
    });
    if (!verifiedSession.access_token) throw new Error("No se recibió una sesión válida.");
    if (flow === "recovery") {
      await post("reset-password", { password: passwordInput.value }, verifiedSession.access_token, "PUT");
      passwordInput.value = "";
      showStatus("Contraseña actualizada. Las sesiones anteriores se cerraron; inicia sesión de nuevo.", "success");
    } else {
      await post("logout", undefined, verifiedSession.access_token);
      showStatus("Correo confirmado. Ya puedes iniciar sesión en Mirage.", "success");
    }
    verifiedSession = null; codeInput.value = "";
    document.getElementById("email-form").hidden = true;
  } catch (error) {
    if (error.code === "session_revoked") verifiedSession = null;
    showStatus(error.message, "error");
  } finally { busy(false); }
});
// Standard Supabase email links arrive with an implicit-flow session in the fragment.
// Remove it from browser history before any requests; never persist or display tokens.
if (linkToken && (linkType === "signup" || linkType === "recovery")) {
  flow = linkType;
  verifiedSession = { access_token: linkToken };
  busy(true);
  showStatus("Comprobando el enlace…");
  post("me", undefined, linkToken, "GET").then(async () => {
    if (flow === "signup") {
      await post("logout", undefined, linkToken);
      verifiedSession = null;
      document.getElementById("email-form").hidden = true;
      document.querySelector("h1").textContent = "Tu espacio te espera.";
      document.getElementById("flow-description").textContent = "Un paso menos. Tu cuenta ya está lista.";
      showStatus("Tu cuenta está confirmada. Ya puedes iniciar sesión en Mirage.", "success");
    } else {
      for (const id of ["email", "code"]) {
        const input = document.getElementById(id);
        input.disabled = true;
        document.getElementById(id + "-field").hidden = true;
      }
      sendButton.hidden = true;
      document.getElementById("flow-description").textContent = "Elige una contraseña nueva para volver a tu espacio.";
      showStatus("Enlace verificado. Escribe tu nueva contraseña.", "success");
      passwordInput.focus();
    }
  }).catch(() => {
    verifiedSession = null;
    showStatus("El enlace no es válido o ya caducó. Solicita un nuevo correo.", "error");
  }).finally(() => busy(false));
} else if (linkParameters.has("error") || linkParameters.has("error_code")) {
  showStatus("El enlace no es válido o ya caducó. Solicita un nuevo correo.", "error");
}
