import { useEffect, useState } from "react";
import { colombiaTime } from "../time.js";
import Shield from "./Shield.jsx";

// Logo, connection state and the Colombia clock.
export default function Header({ connected, error, meta }) {
  const [now, setNow] = useState(Date.now() / 1000);
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => clearInterval(timer);
  }, []);

  let status = "Connecting…";
  let statusClass = "pill pill-wait";
  if (connected) {
    status = "Live";
    statusClass = "pill pill-live";
    if (meta && meta.mode === "dry-run") {
      status = "Live · dry run";
    }
  } else if (error) {
    status = "Aegis unreachable";
    statusClass = "pill pill-down";
  }

  return (
    <header className="header">
      <div className="brand">
        <Shield size={44} />
        <div>
          <h1>Aegis</h1>
          <p>Preventive scaling for Kubernetes</p>
        </div>
      </div>
      <div className="header-right">
        {meta && (
          <span className="target">
            {meta.namespace}/{meta.deployment}
          </span>
        )}
        <span className={statusClass} title={error || ""}>
          <span className="dot" />
          {status}
        </span>
        <span className="clock" title="Colombia time (UTC−5)">
          {colombiaTime(now)} <small>COT</small>
        </span>
      </div>
    </header>
  );
}
