// Small SVG line-chart engine for the dashboard: shared crosshair, one tooltip per chart, no dependencies.
const SVG_NS = "http://www.w3.org/2000/svg";
const MARGIN = { top: 10, right: 14, bottom: 24, left: 48 };
const TIME_STEPS = [5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600, 7200];

function svg(tag, attrs, parent) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attrs || {})) node.setAttribute(key, value);
  if (parent) parent.appendChild(node);
  return node;
}

function html(tag, className, parent, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  if (parent) parent.appendChild(node);
  return node;
}

// 1, 2, 2.5 or 5 times a power of ten, so that about `count` ticks fit in the range.
function niceStep(range, count) {
  const raw = range / Math.max(1, count);
  const power = Math.pow(10, Math.floor(Math.log10(raw)));
  for (const factor of [1, 2, 2.5, 5, 10]) {
    if (raw <= factor * power) return factor * power;
  }
  return 10 * power;
}

function ticks(min, max, step) {
  const out = [];
  const first = Math.ceil(min / step - 1e-9) * step;
  for (let value = first; value <= max + 1e-9; value += step) out.push(Math.round(value * 1e6) / 1e6);
  return out;
}

// Index of the x closest to `value` in a sorted array.
function nearest(xs, value) {
  let low = 0;
  let high = xs.length - 1;
  while (high - low > 1) {
    const middle = (low + high) >> 1;
    if (xs[middle] < value) low = middle;
    else high = middle;
  }
  return Math.abs(xs[low] - value) <= Math.abs(xs[high] - value) ? low : high;
}

// Charts that share the crosshair: hovering one shows the same x on all of them.
export class ChartGroup {
  constructor() {
    this.charts = [];
  }
  add(chart) {
    this.charts.push(chart);
    chart.group = this;
    return chart;
  }
  cursor(x) {
    for (const chart of this.charts) chart.showCursor(x);
  }
}

// One chart: series = [{key, label, color, dash, step, width, dots}], one y axis only.
export class LineChart {
  constructor(container, options) {
    this.options = Object.assign({ height: 180, yMin: 0, yMaxAtLeast: 1, yFormat: (v) => String(v),
      xFormat: (v) => String(v), valueFormat: null, timeTicks: false }, options);
    this.group = null;
    this.data = { x: [], columns: {}, domain: null, rules: [], markers: [], bands: [], zones: [], segments: [] };
    this.root = html("figure", "chart", container);
    const head = html("figcaption", "chart-head", this.root);
    this.titleNode = html("span", "chart-title", head, this.options.title || "");
    if (this.options.unit) html("span", "chart-unit", head, this.options.unit);
    this.legend = html("span", "chart-legend", head);
    if (this.options.note) html("p", "chart-note", this.root, this.options.note);
    this.plot = html("div", "chart-plot", this.root);
    this.plot.tabIndex = 0;
    this.plot.setAttribute("role", "img");
    this.svg = svg("svg", { class: "chart-svg" }, this.plot);
    this.tooltip = html("div", "chart-tooltip", this.plot);
    this.tooltip.hidden = true;
    this.cursorIndex = null;
    this.bindEvents();
    this.renderLegend();
    // Redraw on the next frame and only when the width changed, so drawing never feeds the observer.
    new ResizeObserver(() => {
      if (this.plot.clientWidth === this.lastWidth) return;
      this.lastWidth = this.plot.clientWidth;
      requestAnimationFrame(() => this.render());
    }).observe(this.plot);
  }

  setTitle(text) {
    this.titleNode.textContent = text;
  }

  setSeries(series) {
    this.options.series = series;
    this.renderLegend();
  }

  renderLegend() {
    this.legend.replaceChildren();
    const series = (this.options.series || []).filter((s) => !s.hideInLegend && !s.endLabel);
    if (series.length < 2) return;
    for (const item of series) {
      const entry = html("span", "legend-item", this.legend);
      const key = svg("svg", { width: 18, height: 10, class: "legend-key" }, entry);
      const line = svg("line", { x1: 1, x2: 17, y1: 5, y2: 5 }, key);
      line.style.stroke = item.color;
      line.style.strokeWidth = item.width || 2;
      if (item.dash) line.style.strokeDasharray = item.dash;
      html("span", "", entry, item.label);
    }
  }

  // data: {x, columns: {key: [...]}, domain: [x0, x1], rules: [{y, label}], markers: [{x, label, kind}], bands,
  //        zones: [{x0, x1, label}], now: x, segments: [{x0, y0, x1, y1, color, label}]}
  setData(data) {
    this.data = Object.assign({ rules: [], markers: [], bands: [], zones: [], segments: [] }, data);
    this.render();
  }

  bindEvents() {
    this.plot.addEventListener("pointermove", (event) => {
      if (!this.scale) return;
      const box = this.plot.getBoundingClientRect();
      const x = this.scale.invertX(event.clientX - box.left);
      if (this.group) this.group.cursor(x);
      else this.showCursor(x);
    });
    this.plot.addEventListener("pointerleave", () => {
      if (this.group) this.group.cursor(null);
      else this.showCursor(null);
    });
    this.plot.addEventListener("keydown", (event) => {
      const xs = this.data.x;
      if (!xs.length || (event.key !== "ArrowLeft" && event.key !== "ArrowRight")) return;
      event.preventDefault();
      let index = this.cursorIndex === null ? xs.length - 1 : this.cursorIndex;
      index = Math.max(0, Math.min(xs.length - 1, index + (event.key === "ArrowLeft" ? -1 : 1)));
      if (this.group) this.group.cursor(xs[index]);
      else this.showCursor(xs[index]);
    });
    this.plot.addEventListener("blur", () => this.showCursor(null));
  }

  yRange(x0, x1) {
    let max = this.options.yMaxAtLeast;
    let min = this.options.yMin;
    const xs = this.data.x;
    for (const series of this.options.series || []) {
      const values = this.data.columns[series.key] || [];
      for (let i = 0; i < xs.length; i++) {
        if (xs[i] < x0 || xs[i] > x1 || values[i] === null || values[i] === undefined) continue;
        max = Math.max(max, values[i]);
        if (this.options.yMin === null && (min === null || values[i] < min)) min = values[i];
      }
    }
    for (const rule of this.data.rules) if (rule.y !== null && rule.y !== undefined) max = Math.max(max, rule.y);
    for (const segment of this.data.segments) max = Math.max(max, segment.y0 ?? 0, segment.y1 ?? 0);
    if (min === null) min = 0;
    if (this.options.yMax !== undefined) {
      const step = niceStep(this.options.yMax - min, 4);
      return { min, max: this.options.yMax, step };
    }
    if (max <= min) max = min + 1;
    const step = niceStep(max - min, 4);
    let top = Math.ceil((max * 1.04) / step) * step;
    if (this.options.yCap !== undefined) top = Math.min(top, this.options.yCap);
    return { min: Math.floor(min / step) * step, max: top, step };
  }

  render() {
    const width = this.plot.clientWidth;
    const height = this.options.height;
    if (!width) return;
    this.svg.setAttribute("viewBox", "0 0 " + width + " " + height);
    this.svg.setAttribute("width", width);
    this.svg.setAttribute("height", height);
    this.svg.replaceChildren();
    const xs = this.data.x;
    let [x0, x1] = this.data.domain || [xs[0] ?? 0, xs[xs.length - 1] ?? 1];
    if (x1 <= x0) x1 = x0 + 1;
    const y = this.yRange(x0, x1);
    const left = MARGIN.left;
    const right = width - Math.min(this.options.marginRight ?? MARGIN.right, Math.max(MARGIN.right, width * 0.3));
    const top = MARGIN.top;
    const bottom = height - MARGIN.bottom;
    const sx = (v) => left + ((v - x0) / (x1 - x0)) * (right - left);
    const sy = (v) => bottom - ((v - y.min) / (y.max - y.min)) * (bottom - top);
    this.scale = { sx, sy, invertX: (px) => x0 + ((px - left) / (right - left)) * (x1 - x0), left, right, top, bottom };

    const grid = svg("g", { class: "grid" }, this.svg);
    for (const value of ticks(y.min, y.max, y.step)) {
      svg("line", { x1: left, x2: right, y1: sy(value), y2: sy(value) }, grid);
      const label = svg("text", { x: left - 6, y: sy(value), class: "tick tick-y" }, grid);
      label.textContent = this.options.yFormat(value);
    }
    let xStep = niceStep(x1 - x0, Math.max(2, Math.floor((right - left) / 90)));
    if (this.options.timeTicks) xStep = TIME_STEPS.find((s) => (x1 - x0) / s <= Math.max(2, (right - left) / 90)) || 7200;
    for (const value of ticks(x0, x1, xStep)) {
      const label = svg("text", { x: sx(value), y: bottom + 16, class: "tick tick-x" }, grid);
      label.textContent = this.options.xFormat(value, false, xStep);
    }
    svg("line", { x1: left, x2: right, y1: bottom, y2: bottom, class: "baseline" }, this.svg);

    const clipId = "clip-" + Math.random().toString(36).slice(2);
    const clip = svg("clipPath", { id: clipId }, svg("defs", {}, this.svg));
    svg("rect", { x: left, y: top - 2, width: right - left, height: bottom - top + 4 }, clip);
    const layer = svg("g", { "clip-path": "url(#" + clipId + ")" }, this.svg);

    for (const band of this.data.bands) {
      const rect = svg("rect", { x: left, width: right - left, y: sy(Math.min(band.y1, y.max)),
        height: Math.max(0, sy(Math.max(band.y0, y.min)) - sy(Math.min(band.y1, y.max))), class: "band" }, layer);
      rect.style.fill = band.color;
    }
    for (const zone of this.data.zones) {
      const a = sx(Math.max(zone.x0, x0));
      const b = sx(Math.min(zone.x1, x1));
      if (b <= a) continue;
      svg("rect", { x: a, y: top, width: b - a, height: bottom - top, class: "zone" }, layer);
      if (zone.label) svg("text", { x: a + 6, y: top + 14, class: "zone-label" }, layer).textContent = zone.label;
    }
    for (const marker of this.data.markers) {
      if (marker.x < x0 || marker.x > x1) continue;
      svg("line", { x1: sx(marker.x), x2: sx(marker.x), y1: top, y2: bottom, class: "marker marker-" + marker.kind }, layer);
    }
    for (const rule of this.data.rules) {
      if (rule.y === null || rule.y === undefined || rule.y < y.min || rule.y > y.max) continue;
      svg("line", { x1: left, x2: right, y1: sy(rule.y), y2: sy(rule.y), class: "rule" }, layer);
      const label = svg("text", { x: right - 4, y: sy(rule.y) - 4, class: "rule-label" }, layer);
      label.textContent = rule.label;
    }
    this.endLabels = [];
    for (const series of this.options.series || []) this.drawSeries(layer, series, x0, x1);
    if (this.data.now !== undefined && this.data.now >= x0 && this.data.now <= x1) {
      svg("line", { x1: sx(this.data.now), x2: sx(this.data.now), y1: top - 2, y2: bottom, class: "now" }, layer);
    }
    for (const s of this.data.segments) {
      if (s.y0 === null || s.y1 === null || s.y0 === undefined || s.y1 === undefined) continue;
      const line = svg("line", { x1: sx(s.x0), y1: sy(s.y0), x2: sx(s.x1), y2: sy(s.y1), class: "segment" }, this.svg);
      line.style.stroke = s.color;
      const dot = svg("circle", { cx: sx(s.x1), cy: sy(s.y1), r: 5, class: "segment-dot" }, this.svg);
      dot.style.fill = s.color;
      if (s.label) this.endLabels.push({ y: sy(s.y1) + 4, text: s.label, color: s.color, strong: true });
    }
    for (const marker of this.data.markers) {
      if (marker.x < x0 || marker.x > x1 || !marker.label) continue;
      const label = svg("text", { x: sx(marker.x) + 3, y: top + 9, class: "marker-label marker-" + marker.kind }, this.svg);
      label.textContent = marker.label;
    }
    // Labels in the right margin, at least 17 px apart.
    this.endLabels.sort((a, b) => a.y - b.y);
    for (let i = 1; i < this.endLabels.length; i++) {
      this.endLabels[i].y = Math.max(this.endLabels[i].y, this.endLabels[i - 1].y + 17);
    }
    for (const item of this.endLabels) {
      const label = svg("text", { x: right + 10, y: item.y, class: "end-label" + (item.strong ? " strong" : "") }, this.svg);
      label.textContent = item.text;
      label.style.fill = item.color;
    }
    this.cursorLine = svg("line", { y1: top, y2: bottom, class: "cursor" }, this.svg);
    this.cursorLine.style.display = "none";
    this.cursorDots = svg("g", {}, this.svg);
    this.plot.setAttribute("aria-label", (this.options.title || "") + ": " + this.describe());
    if (this.cursorX !== undefined && this.cursorX !== null) this.showCursor(this.cursorX);
  }

  drawSeries(layer, series, x0, x1) {
    const { sx, sy } = this.scale;
    const xs = this.data.x;
    const values = this.data.columns[series.key] || [];
    let d = "";
    let open = false;
    let lastY = null;
    const dots = [];
    for (let i = 0; i < xs.length; i++) {
      const value = values[i];
      if (value === null || value === undefined || Number.isNaN(value)) {
        if (!series.connect) open = false;
        continue;
      }
      if (xs[i] < x0 && xs[i + 1] !== undefined && xs[i + 1] < x0) continue;
      if (xs[i] > x1 && i > 0 && xs[i - 1] > x1) break;
      const px = sx(xs[i]).toFixed(1);
      const py = sy(value).toFixed(1);
      if (!open) d += "M" + px + "," + py;
      else if (series.step) d += "H" + px + "V" + py;
      else d += "L" + px + "," + py;
      open = true;
      lastY = py;
      if (series.dots) dots.push([px, py]);
    }
    if (series.step && open && lastY !== null && xs.length) d += "H" + sx(Math.min(x1, xs[xs.length - 1] + (this.options.stepTail || 0))).toFixed(1);
    if (d && series.fill) {
      const first = d.match(/^M([\d.-]+)/);
      const last = d.match(/([\d.-]+),[\d.-]+$|H([\d.-]+)$/);
      const endX = last ? (last[1] || last[2]) : null;
      if (first && endX && !d.slice(1).includes("M")) {
        const area = svg("path", { d: d + "V" + this.scale.bottom + "H" + first[1] + "Z", class: "area" }, layer);
        area.style.fill = series.color;
      }
    }
    if (d) {
      const path = svg("path", { d, class: "series" }, layer);
      path.style.stroke = series.color;
      path.style.strokeWidth = series.width || 2;
      if (series.dash) path.style.strokeDasharray = series.dash;
    }
    if (series.endLabel && open && lastY !== null) {
      const lastX = series.step ? sx(Math.min(x1, xs[xs.length - 1] + (this.options.stepTail || 0))) : Number(d.match(/([\d.-]+),[\d.-]+$/)?.[1]);
      this.endLabels.push({ y: Number(lastY) + 4, text: series.endLabel, color: series.color });
    }
    for (const [px, py] of dots) {
      const dot = svg("circle", { cx: px, cy: py, r: 4, class: "dot" }, layer);
      dot.style.fill = series.color;
    }
  }

  // Short text description of the latest values, for screen readers.
  describe() {
    const parts = [];
    const xs = this.data.x;
    for (const series of this.options.series || []) {
      const values = this.data.columns[series.key] || [];
      for (let i = xs.length - 1; i >= 0; i--) {
        if (values[i] !== null && values[i] !== undefined) {
          parts.push(series.label + " " + this.format(values[i], series));
          break;
        }
      }
    }
    return parts.join(", ");
  }

  format(value, series) {
    if (value === null || value === undefined) return "–";
    if (series && series.format) return series.format(value);
    if (this.options.valueFormat) return this.options.valueFormat(value);
    return this.options.yFormat(value);
  }

  showCursor(x) {
    this.cursorX = x;
    const xs = this.data.x;
    if (!this.scale || x === null || x === undefined || !xs.length) {
      if (this.cursorLine) this.cursorLine.style.display = "none";
      if (this.cursorDots) this.cursorDots.replaceChildren();
      this.tooltip.hidden = true;
      this.cursorIndex = null;
      return;
    }
    const index = nearest(xs, x);
    const [x0, x1] = this.data.domain || [xs[0], xs[xs.length - 1]];
    if (xs[index] < x0 || xs[index] > x1) {
      this.showCursor(null);
      return;
    }
    this.cursorIndex = index;
    const { sx, sy, left, right } = this.scale;
    const px = sx(xs[index]);
    this.cursorLine.setAttribute("x1", px);
    this.cursorLine.setAttribute("x2", px);
    this.cursorLine.style.display = "";
    this.cursorDots.replaceChildren();
    this.tooltip.replaceChildren();
    html("div", "tooltip-x", this.tooltip, this.options.xFormat(xs[index], true));
    for (const series of this.options.series || []) {
      if (series.hideInTooltip) continue;
      const value = (this.data.columns[series.key] || [])[index];
      const row = html("div", "tooltip-row", this.tooltip);
      const key = svg("svg", { width: 14, height: 8, class: "legend-key" }, row);
      const line = svg("line", { x1: 1, x2: 13, y1: 4, y2: 4 }, key);
      line.style.stroke = series.color;
      line.style.strokeWidth = 2.5;
      if (series.dash) line.style.strokeDasharray = series.dash;
      html("strong", "", row, this.format(value, series));
      html("span", "", row, series.label);
      if (value !== null && value !== undefined) {
        const dot = svg("circle", { cx: px, cy: sy(value), r: 4, class: "cursor-dot" }, this.cursorDots);
        dot.style.fill = series.color;
      }
    }
    this.tooltip.hidden = false;
    const width = this.tooltip.offsetWidth;
    const placeLeft = px + 14 + width > right;
    this.tooltip.style.left = (placeLeft ? Math.max(left, px - 14 - width) : px + 14) + "px";
  }
}
