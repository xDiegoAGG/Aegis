export const WINDOWS = [
  { label: "5 min", seconds: 300 },
  { label: "15 min", seconds: 900 },
  { label: "30 min", seconds: 1800 },
];

// Traffic cannot be negative: a falling trend projects below 0.
export function atLeastZero(number) {
  if (number === null) {
    return null;
  }
  return Math.max(0, number);
}

function value(number, scale = 1, decimals = 2) {
  if (number === null || number === undefined || Number.isNaN(number)) {
    return null;
  }
  return Number((number * scale).toFixed(decimals));
}

// The points of the four charts for the cycles inside the window that ends at `now` (unix seconds).
export function buildPoints(records, meta, windowSeconds, now) {
  const capacity = meta ? meta.pod_capacity_rps : null;
  const start = now - windowSeconds;
  const points = [];
  for (const record of records) {
    if (record.time < start) {
      continue;
    }
    let readyCapacity = null;
    if (capacity && record.replicas_ready !== null && record.replicas_ready !== undefined) {
      readyCapacity = value(capacity * record.replicas_ready, 1, 1);
    }
    points.push({
      t: record.time,
      rps: value(record.rps, 1, 1),
      projected: atLeastZero(value(record.projected_rps, 1, 1)),
      capacity: readyCapacity,
      risk: value(record.risk, 100, 1),
      requested: record.target,
      ready: record.replicas_ready,
      hpa: record.hpa_desired === undefined ? null : record.hpa_desired,
      p95: value(record.p95_s, 1, 3),
    });
  }
  return points;
}

// The scale-ups and scale-downs inside the window, to mark them on the charts.
export function decisionMarks(records, windowSeconds, now) {
  const start = now - windowSeconds;
  const marks = [];
  for (const record of records) {
    if (record.time < start || record.action === "hold") {
      continue;
    }
    marks.push({
      t: record.time,
      action: record.action,
      from: record.previous_target,
      to: record.target,
      reason: record.reason,
      risk: value(record.risk, 100, 1),
    });
  }
  return marks;
}

// The highest value of some keys, so an axis always leaves room above its reference line.
export function highest(points, keys, floor) {
  let top = floor;
  for (const point of points) {
    for (const key of keys) {
      if (point[key] !== null && point[key] > top) {
        top = point[key];
      }
    }
  }
  return top;
}
