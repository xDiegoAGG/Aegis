export const API_URL = (import.meta.env.VITE_AEGIS_API_URL || "").replace(/\/$/, "");
export const MAX_RECORDS = 1440;

// Adds the new cycles after the ones already kept, without repeats, and keeps the last maxRecords.
export function mergeRecords(current, incoming, maxRecords = MAX_RECORDS) {
  let last = -Infinity;
  if (current.length > 0) {
    last = current[current.length - 1].time;
  }
  const merged = current.slice();
  for (const record of incoming) {
    if (record.time > last) {
      merged.push(record);
      last = record.time;
    }
  }
  if (merged.length > maxRecords) {
    return merged.slice(merged.length - maxRecords);
  }
  return merged;
}

export function lastTime(records) {
  if (records.length === 0) {
    return null;
  }
  return records[records.length - 1].time;
}

// One poll of /api/state: only the cycles after `since`.
export async function fetchState(since, signal) {
  let url = API_URL + "/api/state";
  if (since !== null && since !== undefined) {
    url += "?since=" + since;
  }
  const response = await fetch(url, { signal, cache: "no-store" });
  if (!response.ok) {
    throw new Error("Aegis answered " + response.status);
  }
  return response.json();
}
