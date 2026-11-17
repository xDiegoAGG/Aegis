import { useEffect, useState } from "react";
import Cards from "./components/Cards.jsx";
import Charts from "./components/Charts.jsx";
import Decisions from "./components/Decisions.jsx";
import Header from "./components/Header.jsx";
import LoadPanel from "./components/LoadPanel.jsx";
import { WINDOWS, buildPoints, decisionMarks } from "./series.js";
import { useAegis } from "./useAegis.js";

// The live monitor: state cards, load buttons, the four charts and the decisions, all from /api/state.
export default function App() {
  const { meta, records, connected, error } = useAegis();
  const [windowSeconds, setWindowSeconds] = useState(WINDOWS[0].seconds);
  const [now, setNow] = useState(Date.now() / 1000);
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => clearInterval(timer);
  }, []);

  const points = buildPoints(records, meta, windowSeconds, now);
  const marks = decisionMarks(records, windowSeconds, now);

  return (
    <div className="page">
      <Header connected={connected} error={error} meta={meta} />
      <main>
        <Cards meta={meta} records={records} />
        <LoadPanel />
        <div className="toolbar">
          <span>Times in Colombia (UTC−5)</span>
          <div className="segmented">
            {WINDOWS.map((option) => (
              <button
                key={option.seconds}
                className={option.seconds === windowSeconds ? "selected" : ""}
                onClick={() => setWindowSeconds(option.seconds)}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>
        <Charts points={points} marks={marks} meta={meta} start={now - windowSeconds} end={now} />
        <Decisions records={records} />
      </main>
      <footer className="footer">Aegis projects the traffic, computes the risk and raises the HPA minReplicas before the pods run short.</footer>
    </div>
  );
}
