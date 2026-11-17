import { useEffect, useState } from "react";
import { durationText } from "../time.js";
import { KEY_STORAGE, fetchLoads, loadProgress, startLoad, stopLoad } from "../loads.js";

const LABELS = {
  ramp: { title: "Ramp", hint: "climbs for 2 min: Aegis sees it coming" },
  spike: { title: "Spike", hint: "jumps in 5 s: nothing to anticipate" },
  waves: { title: "Waves", hint: "two waves: up and back down twice" },
};

// The buttons that send real traffic (k6 in the cluster) while the charts show how Aegis reacts.
export default function LoadPanel() {
  const [key, setKey] = useState(() => localStorage.getItem(KEY_STORAGE) || "");
  const [status, setStatus] = useState(null);
  const [message, setMessage] = useState(null);
  const [busy, setBusy] = useState(false);
  const [now, setNow] = useState(Date.now() / 1000);

  async function refresh() {
    try {
      setStatus(await fetchLoads());
    } catch (problem) {
      setStatus(null);
    }
  }

  useEffect(() => {
    refresh();
    const poll = setInterval(refresh, 5000);
    const tick = setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => {
      clearInterval(poll);
      clearInterval(tick);
    };
  }, []);

  function saveKey(text) {
    setKey(text);
    localStorage.setItem(KEY_STORAGE, text);
  }

  async function run(action) {
    setBusy(true);
    setMessage(null);
    const result = await action();
    if (!result.ok) {
      setMessage(result.error);
    }
    await refresh();
    setBusy(false);
  }

  const running = status ? status.running : null;
  const enabled = status ? status.enabled : false;
  const progress = loadProgress(running, now);

  return (
    <section className="loads">
      <div className="loads-head">
        <h2>Send traffic</h2>
        <p>Real requests from k6 inside the cluster, scaled to C = {status ? status.capacity_rps : "…"} req/s per pod.</p>
      </div>
      <div className="loads-row">
        {(status ? status.profiles : []).map((profile) => {
          const label = LABELS[profile.name] || { title: profile.name, hint: "" };
          return (
            <button
              key={profile.name}
              className={"load-button load-" + profile.name + (running && running.profile === profile.name ? " active" : "")}
              disabled={busy || !enabled || Boolean(running)}
              onClick={() => run(() => startLoad(key, profile.name))}
              title={label.hint}
            >
              <span className="load-title">{label.title}</span>
              <span className="load-meta">
                {durationText(profile.seconds)} · up to {profile.peak_rps} req/s
              </span>
            </button>
          );
        })}
        <button className="stop-button" disabled={busy || !enabled || !running} onClick={() => run(() => stopLoad(key))}>
          Stop
        </button>
        <label className="key">
          <span>Load key</span>
          <input type="password" value={key} placeholder="paste the key" onChange={(event) => saveKey(event.target.value)} autoComplete="off" />
        </label>
      </div>
      {running && (
        <div className="progress">
          <div className="progress-bar" style={{ width: progress * 100 + "%" }} />
          <span>
            {(LABELS[running.profile] || { title: running.profile }).title} running ·{" "}
            {durationText(Math.max(0, running.ends_at - now))} left
          </span>
        </div>
      )}
      {status && !enabled && <p className="note">The buttons are off: this Aegis has no load key (AEGIS_LOAD_KEY).</p>}
      {!status && <p className="note">Waiting for Aegis…</p>}
      {message && <p className="error">{message}</p>}
    </section>
  );
}
