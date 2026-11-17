import { colombiaTime } from "../time.js";

function show(number, decimals, unit) {
  if (number === null || number === undefined) {
    return "–";
  }
  return Number(number).toFixed(decimals) + (unit || "");
}

function riskLevel(risk, meta) {
  if (risk === null || risk === undefined || !meta) {
    return "";
  }
  if (risk >= meta.scale_up_threshold) {
    return "card-alert";
  }
  if (risk >= meta.scale_down_threshold) {
    return "card-warn";
  }
  return "card-ok";
}

function Card({ label, value, detail, className }) {
  return (
    <div className={"card " + (className || "")}>
      <span className="card-label">{label}</span>
      <span className="card-value">{value}</span>
      {detail && <span className="card-detail">{detail}</span>}
    </div>
  );
}

// The numbers of the last cycle and the calibration, and the last decision Aegis took.
export default function Cards({ meta, records }) {
  const last = records.length > 0 ? records[records.length - 1] : null;
  let decision = null;
  for (let index = records.length - 1; index >= 0; index -= 1) {
    if (records[index].action !== "hold") {
      decision = records[index];
      break;
    }
  }
  const latency = meta ? meta.p95_threshold_seconds : null;
  return (
    <section className="cards">
      <Card
        label="Demand"
        value={show(last && last.rps, 1, " req/s")}
        detail={"projected " + show(last && last.projected_rps, 1, " req/s")}
      />
      <Card
        label="Risk"
        value={show(last && last.risk !== null ? last.risk * 100 : null, 0, "%")}
        detail={meta ? "up at " + meta.scale_up_threshold * 100 + "%, down under " + meta.scale_down_threshold * 100 + "%" : ""}
        className={riskLevel(last && last.risk, meta)}
      />
      <Card
        label="Pods"
        value={last ? show(last.replicas_ready, 0) + " / " + show(last.target, 0) : "–"}
        detail="Ready / requested by Aegis"
      />
      <Card
        label="Latency P95"
        value={show(last && last.p95_s, 2, " s")}
        detail={latency ? "slow above L = " + latency + " s" : ""}
        className={last && latency && last.p95_s > latency ? "card-alert" : ""}
      />
      <Card
        label="Calibration"
        value={meta ? "C " + show(meta.pod_capacity_rps, 0) + " · T " + show(meta.startup_time_seconds, 0) + " s" : "–"}
        detail="req/s per pod · pod startup"
      />
      <Card label="σ" value={show(last && last.sigma_rps, 1, " req/s")} detail="projection error, learned live" />
      <Card
        label="Last decision"
        value={decision ? (decision.action === "scale_up" ? "▲ " : "▼ ") + decision.previous_target + " → " + decision.target : "none yet"}
        detail={decision ? colombiaTime(decision.time) + " · " + decision.reason : "Aegis holds while the risk is low"}
        className={decision ? (decision.action === "scale_up" ? "card-up" : "card-down") : ""}
      />
    </section>
  );
}
