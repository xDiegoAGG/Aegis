import { colombiaTime } from "../time.js";

// The last scale-ups and scale-downs, newest first, with the reason Aegis gave.
export default function Decisions({ records }) {
  const found = [];
  for (let index = records.length - 1; index >= 0 && found.length < 8; index -= 1) {
    if (records[index].action !== "hold") {
      found.push(records[index]);
    }
  }
  return (
    <section className="decisions">
      <h2>Decisions</h2>
      {found.length === 0 && <p className="note">No scaling yet. Send traffic with a button above.</p>}
      <ul>
        {found.map((record) => (
          <li key={record.time} className={record.action === "scale_up" ? "up" : "down"}>
            <span className="when">{colombiaTime(record.time)}</span>
            <span className="what">
              {record.action === "scale_up" ? "▲ Scale up" : "▼ Scale down"} {record.previous_target} → {record.target}
            </span>
            <span className="why">{record.reason}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
