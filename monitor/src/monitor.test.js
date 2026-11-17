import { describe, expect, it } from "vitest";
import { mergeRecords } from "./api.js";
import { loadErrorMessage, loadProgress } from "./loads.js";
import { buildPoints, decisionMarks, highest } from "./series.js";
import { colombiaShort, colombiaTime, durationText } from "./time.js";

const META = { pod_capacity_rps: 24, max_replicas: 3 };

function record(time, extra) {
  return {
    time,
    rps: 10,
    projected_rps: 12,
    risk: 0.1,
    target: 1,
    previous_target: 1,
    replicas_ready: 1,
    hpa_desired: 1,
    p95_s: 0.2,
    action: "hold",
    reason: "",
    ...extra,
  };
}

describe("Colombia time", () => {
  it("is UTC-5 whatever the zone of this machine", () => {
    expect(colombiaTime(0)).toBe("19:00:00");
    expect(colombiaTime(Date.UTC(2026, 10, 17, 15, 4, 5) / 1000)).toBe("10:04:05");
    expect(colombiaShort(Date.UTC(2026, 6, 1, 3, 30) / 1000)).toBe("22:30");
  });

  it("writes durations as minutes and seconds", () => {
    expect(durationText(240)).toBe("4:00");
    expect(durationText(65.4)).toBe("1:05");
    expect(durationText(-3)).toBe("0:00");
  });
});

describe("merging the polls", () => {
  it("keeps the order, drops repeats and keeps the last ones", () => {
    const kept = mergeRecords([record(1), record(2)], [record(2), record(3), record(4)], 3);
    expect(kept.map((item) => item.time)).toEqual([2, 3, 4]);
  });
});

describe("chart series", () => {
  it("keeps only the window and leaves missing values empty", () => {
    const records = [record(100), record(400, { rps: null, p95_s: null, risk: 0.756, replicas_ready: 2 })];
    const points = buildPoints(records, META, 300, 450);
    expect(points).toHaveLength(1);
    expect(points[0].rps).toBeNull();
    expect(points[0].p95).toBeNull();
    expect(points[0].risk).toBe(75.6);
    expect(points[0].capacity).toBe(48);
    expect(buildPoints([record(400, { projected_rps: -9.6 })], META, 300, 450)[0].projected).toBe(0);
  });

  it("marks only scale-ups and scale-downs", () => {
    const records = [
      record(10),
      record(15, { action: "scale_up", previous_target: 1, target: 2 }),
      record(20, { action: "scale_down", previous_target: 2, target: 1 }),
    ];
    const marks = decisionMarks(records, 300, 30);
    expect(marks.map((mark) => mark.action)).toEqual(["scale_up", "scale_down"]);
    expect(marks[0].to).toBe(2);
  });

  it("finds the top of an axis", () => {
    expect(highest([{ a: 3, b: null }, { a: 9, b: 12 }], ["a", "b"], 5)).toBe(12);
    expect(highest([], ["a"], 5)).toBe(5);
  });
});

describe("load buttons", () => {
  it("explains every error", () => {
    expect(loadErrorMessage(401)).toMatch(/key/);
    expect(loadErrorMessage(409)).toMatch(/running/);
    expect(loadErrorMessage(500)).toMatch(/500/);
  });

  it("tracks the progress of the running load", () => {
    const running = { started_at: 100, ends_at: 200 };
    expect(loadProgress(running, 150)).toBe(0.5);
    expect(loadProgress(running, 300)).toBe(1);
    expect(loadProgress(null, 150)).toBe(0);
  });
});
