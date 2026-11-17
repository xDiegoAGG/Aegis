import { API_URL } from "./api.js";

export const KEY_STORAGE = "aegis-load-key";

const MESSAGES = {
  400: "Unknown load profile.",
  401: "Wrong key: check the load key.",
  403: "The load buttons are off: Aegis has no AEGIS_LOAD_KEY.",
  409: "Another load is still running. Stop it first.",
  502: "Kubernetes did not create or delete the k6 Job.",
};

// A clear sentence for an HTTP status of /api/load.
export function loadErrorMessage(status) {
  return MESSAGES[status] || "Aegis did not answer (" + status + ").";
}

async function call(method, key, body) {
  const options = { method, headers: { "X-Aegis-Key": key || "" } };
  if (body) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  let response;
  try {
    response = await fetch(API_URL + "/api/load", options);
  } catch (problem) {
    return { ok: false, error: "Aegis cannot be reached." };
  }
  if (!response.ok) {
    return { ok: false, status: response.status, error: loadErrorMessage(response.status) };
  }
  return { ok: true, body: await response.json() };
}

export function startLoad(key, profile) {
  return call("POST", key, { profile });
}

export function stopLoad(key) {
  return call("DELETE", key, null);
}

export async function fetchLoads() {
  const response = await fetch(API_URL + "/api/load", { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Aegis answered " + response.status);
  }
  return response.json();
}

// Share of the running load already sent (0 to 1).
export function loadProgress(running, now) {
  if (!running) {
    return 0;
  }
  const total = running.ends_at - running.started_at;
  if (total <= 0) {
    return 1;
  }
  return Math.min(1, Math.max(0, (now - running.started_at) / total));
}
