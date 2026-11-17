import { useEffect, useRef, useState } from "react";
import { fetchState, lastTime, mergeRecords } from "./api.js";

const POLL_MS = 2000;

// Polls Aegis every 2 s and keeps its cycles; a new session (Aegis restarted) starts over.
export function useAegis() {
  const [data, setData] = useState({ meta: null, records: [], actions: null });
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState(null);
  const latest = useRef({ session: null, records: [] });

  useEffect(() => {
    let stopped = false;
    let timer = null;
    const controller = new AbortController();

    async function poll() {
      try {
        const kept = latest.current;
        const body = await fetchState(lastTime(kept.records), controller.signal);
        let records = kept.records;
        if (body.meta.session !== kept.session) {
          records = [];
        }
        records = mergeRecords(records, body.records);
        latest.current = { session: body.meta.session, records };
        if (!stopped) {
          setData({ meta: body.meta, records, actions: body.actions });
          setConnected(true);
          setError(null);
        }
      } catch (problem) {
        if (!stopped && problem.name !== "AbortError") {
          setConnected(false);
          setError(problem.message);
        }
      }
      if (!stopped) {
        timer = setTimeout(poll, POLL_MS);
      }
    }

    poll();
    return () => {
      stopped = true;
      controller.abort();
      clearTimeout(timer);
    };
  }, []);

  return { ...data, connected, error };
}
