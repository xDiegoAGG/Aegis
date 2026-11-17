import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { highest } from "../series.js";
import { colombiaShort, colombiaTime } from "../time.js";

const COLORS = {
  demand: "#2563eb",
  projected: "#7c3aed",
  capacity: "#475569",
  risk: "#ea580c",
  up: "#d97706",
  down: "#059669",
  aegis: "#2563eb",
  ready: "#0f172a",
  hpa: "#ea580c",
  p95: "#0d9488",
  slow: "#dc2626",
  grid: "#eef1f5",
  axis: "#94a3b8",
};

// Axis ticks on round Colombia minutes: every minute for 5 min, every 3 for 15, every 5 for 30.
function minuteTicks(start, end) {
  const span = end - start;
  let step = 60;
  if (span > 600) {
    step = 180;
  }
  if (span > 1200) {
    step = 300;
  }
  const ticks = [];
  for (let tick = Math.ceil(start / step) * step; tick <= end; tick += step) {
    ticks.push(tick);
  }
  return ticks;
}

function TooltipBox({ active, payload, label, unit }) {
  if (!active || !payload || payload.length === 0) {
    return null;
  }
  return (
    <div className="tooltip">
      <strong>{colombiaTime(label)}</strong>
      {payload.map((item) => (
        <div key={item.dataKey} className="tooltip-row">
          <span className="swatch" style={{ background: item.color }} />
          {item.name}: <b>{item.value === null || item.value === undefined ? "–" : item.value}</b> {unit}
        </div>
      ))}
    </div>
  );
}

function Frame({ title, subtitle, children }) {
  return (
    <div className="chart">
      <div className="chart-head">
        <h3>{title}</h3>
        <span>{subtitle}</span>
      </div>
      <div className="chart-body">
        <ResponsiveContainer width="100%" height="100%">
          {children}
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function marksOn(marks) {
  return marks.map((mark) => (
    <ReferenceLine
      key={mark.t}
      x={mark.t}
      stroke={mark.action === "scale_up" ? COLORS.up : COLORS.down}
      strokeDasharray="3 3"
      label={{
        value: (mark.action === "scale_up" ? "▲" : "▼") + mark.to,
        position: "insideTop",
        fill: mark.action === "scale_up" ? COLORS.up : COLORS.down,
        fontSize: 11,
      }}
    />
  ));
}

// The four live charts, on the same Colombia-time axis: traffic, risk, pods and latency.
export default function Charts({ points, marks, meta, start, end }) {
  const ticks = minuteTicks(start, end);
  const axis = {
    dataKey: "t",
    type: "number",
    domain: [start, end],
    ticks,
    tickFormatter: colombiaShort,
    stroke: COLORS.axis,
    fontSize: 11,
    allowDataOverflow: true,
  };
  const yAxis = { stroke: COLORS.axis, fontSize: 11, width: 40 };
  const common = { data: points, syncId: "aegis", margin: { top: 16, right: 12, bottom: 0, left: 0 } };
  const latency = meta ? meta.p95_threshold_seconds : 1;
  const upPct = meta ? meta.scale_up_threshold * 100 : 70;
  const downPct = meta ? meta.scale_down_threshold * 100 : 30;
  const maxPods = meta ? meta.max_replicas : 3;
  const rpsTop = Math.ceil(highest(points, ["rps", "projected", "capacity"], 10) * 1.1);
  const p95Top = Math.max(latency * 1.5, highest(points, ["p95"], 0) * 1.1);

  return (
    <section className="charts">
      <Frame title="Requests per second" subtitle="demand, what Aegis expects T + 20 s ahead, and what the Ready pods can serve (C × pods)">
        <ComposedChart {...common}>
          <CartesianGrid stroke={COLORS.grid} />
          <XAxis {...axis} />
          <YAxis {...yAxis} domain={[0, rpsTop]} />
          <Tooltip content={<TooltipBox unit="req/s" />} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Area name="Demand" dataKey="rps" stroke={COLORS.demand} fill={COLORS.demand} fillOpacity={0.1} strokeWidth={2} isAnimationActive={false} connectNulls />
          <Line name="Projection" dataKey="projected" stroke={COLORS.projected} strokeDasharray="5 4" dot={false} isAnimationActive={false} connectNulls />
          <Line name="Capacity" dataKey="capacity" type="stepAfter" stroke={COLORS.capacity} strokeWidth={2} dot={false} isAnimationActive={false} connectNulls />
          {marksOn(marks)}
        </ComposedChart>
      </Frame>

      <Frame title="Risk of running short" subtitle={"Aegis asks for one more pod at " + upPct + "% and gives pods back under " + downPct + "%"}>
        <ComposedChart {...common}>
          <CartesianGrid stroke={COLORS.grid} />
          <XAxis {...axis} />
          <YAxis {...yAxis} domain={[0, 100]} unit="%" />
          <Tooltip content={<TooltipBox unit="%" />} />
          <ReferenceLine y={upPct} stroke={COLORS.up} strokeDasharray="6 4" label={{ value: upPct + "% up", fill: COLORS.up, fontSize: 11, position: "insideTopRight" }} />
          <ReferenceLine y={downPct} stroke={COLORS.down} strokeDasharray="6 4" label={{ value: downPct + "% down", fill: COLORS.down, fontSize: 11, position: "insideBottomRight" }} />
          <Area name="Risk" dataKey="risk" stroke={COLORS.risk} fill={COLORS.risk} fillOpacity={0.15} strokeWidth={2} isAnimationActive={false} connectNulls />
          {marksOn(marks)}
        </ComposedChart>
      </Frame>

      <Frame title="Pods" subtitle="requested by Aegis (HPA minReplicas), Ready, and what the HPA itself wants">
        <ComposedChart {...common}>
          <CartesianGrid stroke={COLORS.grid} />
          <XAxis {...axis} />
          <YAxis {...yAxis} domain={[0, maxPods + 0.5]} allowDecimals={false} ticks={Array.from({ length: maxPods + 1 }, (item, index) => index)} />
          <Tooltip content={<TooltipBox unit="pods" />} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Line name="Aegis asks" dataKey="requested" type="stepAfter" stroke={COLORS.aegis} strokeWidth={3} dot={false} isAnimationActive={false} connectNulls />
          <Line name="Ready" dataKey="ready" type="stepAfter" stroke={COLORS.ready} strokeWidth={2} dot={false} isAnimationActive={false} connectNulls />
          <Line name="HPA wants" dataKey="hpa" type="stepAfter" stroke={COLORS.hpa} strokeDasharray="4 4" dot={false} isAnimationActive={false} connectNulls />
        </ComposedChart>
      </Frame>

      <Frame title="Latency P95" subtitle={"at the entrance (Traefik); above L = " + latency + " s the service counts as slow"}>
        <ComposedChart {...common}>
          <CartesianGrid stroke={COLORS.grid} />
          <XAxis {...axis} />
          <YAxis {...yAxis} domain={[0, Number(p95Top.toFixed(1))]} unit=" s" width={48} />
          <Tooltip content={<TooltipBox unit="s" />} />
          <ReferenceLine y={latency} stroke={COLORS.slow} strokeDasharray="6 4" label={{ value: "L = " + latency + " s", fill: COLORS.slow, fontSize: 11, position: "insideTopRight" }} />
          <Area name="P95" dataKey="p95" stroke={COLORS.p95} fill={COLORS.p95} fillOpacity={0.1} strokeWidth={2} isAnimationActive={false} connectNulls />
        </ComposedChart>
      </Frame>
    </section>
  );
}
