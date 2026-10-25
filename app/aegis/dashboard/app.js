import { ChartGroup, LineChart } from "./plot.js";

const POLL_MS = 2000;
const RUN_COLORS = ["var(--run-1)", "var(--run-2)", "var(--run-3)", "var(--run-4)"];
const MAX_RUNS = 3;

const TEXT = {
  es: {
    tabLive: "En vivo", tabExperiments: "Experimentos", all: "Todo",
    waitingTitle: "Esperando el primer ciclo de Aegis",
    waitingBody: "Este panel lo sirve Aegis. Arráncalo en vivo o reproduce una corrida grabada:",
    versusTitle: "Aegis frente al HPA solo, con la misma carga",
    versusLead: "Con esta misma carga, el HPA solo dejó fallar <b>{hpa} %</b> de las peticiones; con Aegis, <b>{aegis} %</b>. Aegis pidió el 2º pod <b>{gain} s antes</b>.",
    vsAegis: "Aegis (esta corrida)", vsHpa: "Solo HPA (corrida mediana)",
    vsAsk: "Pide el 2º pod", vsFailed: "Peticiones fallidas", vsSlow: "Segundos con el servicio lento", vsCost: "Costo (pods-minuto)",
    vsBefore: "{s} s, {d} s antes de superar un pod", vsAfter: "{s} s, {d} s después de superar un pod", vsNever: "nunca",
    vsNote: "Resultados finales de cada corrida, medidos por k6 desde el cliente. Solo HPA: {n} corridas, fallos entre {min} y {max} %. En «Últimos minutos», la línea gris es la capacidad que tuvo el HPA solo en el mismo momento de la carga.",
    vsMissing: "Esta carga no se probó con el HPA solo. Elige la prueba 1 (rampa) o la 4 (pico) para ver la comparación.",
    lHpa: "capacidad del HPA solo",
    profiles: { linear: "rampa", fluctuating: "olas", spike: "pico", "ramp-045": "rampa rápida", "ramp-050": "rampa más rápida" },
    replayPick: "Corrida grabada que se reproduce", replayNote: "Prueba {n}: {desc}", replayError: "No se pudo cambiar la corrida: {e}",
    test1: "una rampa de 5 a 46 req/s en 2 minutos, 1 minuto arriba y bajada.",
    test2: "dos olas de tráfico (hasta 28 y hasta 46 req/s) con 2 minutos de tráfico bajo después de cada una. Aegis sube en cada ola y devuelve los pods entre ellas.",
    test4: "un salto de 5 a 41 req/s en 5 segundos, sin tendencia previa: no se puede anticipar.",
    test6: "una rampa más rápida (0.41 req/s por segundo).",
    test7: "una rampa más rápida (0.46 req/s por segundo).",
    test8: "la rampa de la prueba 1, con el HPA leyendo la decisión de Aegis por la Custom Metrics API.",
    testOther: "una corrida guardada.",
    stateLive: "En vivo", stateReplay: "Reproduciendo", stateDry: "Dry-run, sin aplicar", stateOffline: "Sin conexión con Aegis",
    lastCycle: "último ciclo hace {s} s", speed: "a ×{v}",
    vOverflow: "Los pods no alcanzan.", vScale: "En {h} s no alcanzarían: Aegis pide otro pod.",
    vShrink: "Sobra un pod: Aegis lo apaga.", vNear: "Alcanzan, pero están cerca del límite.", vWaiting: "Al límite hasta que el pod {n} esté listo.", vCalm: "Los pods alcanzan con holgura.",
    vNoData: "Sin datos de tráfico en este ciclo.",
    detail: "Llegan <b>{r} req/s</b>. {ready} {readyWord} {serveVerb} <b>{cap} req/s</b> ({c} cada uno). En {h} s se esperan <b>{p} req/s</b>: probabilidad de no alcanzar, {risk}.",
    starting: " {n} más {verb} pedido pero aún no listo.", startingOne: "está", startingMany: "están",
    pod: "pod", pods: "pods", podN: "Pod {n}", serveOne: "aguanta", serveMany: "aguantan",
    tankLoad: "al {v} %", tankStarting: "aún no listo", tankOff: "apagado",
    tankOverflow: "{v} req/s sin atender",
    tankKey: "El agua es el tráfico que recibe cada pod (Traefik lo reparte por igual). La línea ámbar es el nivel esperado en {h} s. Un pod punteado no está listo: está arrancando, o está tan saturado que no responde a su chequeo de salud.",
    historyTitle: "Últimos minutos", decisionsTitle: "Qué hizo Aegis",
    lTraffic: "tráfico", lCapacity: "capacidad (pods listos)", lForecast: "en {h} s",
    upEvent: "Pidió el pod {n}", downEvent: "Apagó el pod {n}",
    upWhy: "En {h} s esperaba {p} req/s y {n} {podsWord} {serveVerb} {cap}. Probabilidad de no alcanzar: {risk}.",
    downWhy: "El tráfico bajó: con {n} {podsWord} la probabilidad de no alcanzar llevaba 60 s bajo {down}, así que sobraba uno.",
    noDecisions: "Todavía no cambió nada: Aegis mantiene los pods.",
    markUp: "+1 pod", markDown: "−1 pod",
    techTitle: "Cómo decide Aegis", techHint: "La fórmula y las señales que usa en cada ciclo",
    fDemand: "tráfico que llega", fTrend: "cuánto sube por segundo", fHorizon: "lo que tarda un pod en estar listo (T + retraso)",
    fForecast: "tráfico esperado", fCapacity: "lo que aguantan los pods pedidos", fError: "cuánto se equivoca la proyección",
    fRisk: "probabilidad de no alcanzar", fRule: "Pide un pod si pasa de {up}. Apaga uno si, con un pod menos, se queda bajo {down} durante 60 s.",
    chartForecast: "Qué tan bien predice", chartForecastNote: "Cada proyección dibujada en el momento al que apuntaba, junto al tráfico que de verdad llegó.",
    chartRisk: "Probabilidad de no alcanzar en 35 s", chartRiskNote: "Sobre la línea de 70 % Aegis pide un pod. La línea gris es la misma cuenta con un pod menos: si se queda bajo 30 % durante 60 s, apaga uno.",
    chartPods: "Pods", chartPodsNote: "Los que pidió Aegis, los que ya están listos y lo que hace el HPA.",
    chartLatency: "Lentitud (P95)", chartLatencyNote: "El 95 % de las peticiones tarda menos que esto. Sobre 1 s el servicio se considera lento.",
    chartSigma: "Error de la proyección (σ)", chartSigmaNote: "Cuánto se ha equivocado últimamente hacia arriba. Más error, más cautela.",
    chartSlope: "Tendencia (m)", chartSlopeNote: "Cuántas req/s sube o baja el tráfico por segundo.",
    sDemand: "llegó", sProjected: "había proyectado", sRisk: "con los pods pedidos", sRiskLess: "con un pod menos",
    sTarget: "pedidos", sReady: "listos", sHpa: "deseados por el HPA", sP95: "P95", sSigma: "σ", sSlope: "m",
    ruleUp: "pide en {v}", ruleDown: "apaga bajo {v}", ruleL: "lento sobre {v} s",
    paramsTitle: "Parámetros", cyclesTitle: "Todos los ciclos en tabla",
    pC: "Capacidad de un pod", pT: "Arranque de un pod", pLag: "Retraso de la medición", pWindow: "Ventana de tendencia",
    pL: "Umbral de lentitud", pTd: "Tiempo sostenido", pUp: "Umbral para pedir", pDown: "Umbral para apagar",
    pDownWait: "Espera para apagar", pRange: "Rango de pods", pMode: "Cómo actúa", pCalibrated: "Calibrado",
    modeMin: "escribe minReplicas", modeMetric: "publica una métrica",
    colTime: "hora", colAction: "pods", colReason: "motivo",
    experimentsTitle: "Corridas grabadas",
    runHint: "Marca hasta 3 para verlas sobre el mismo eje, en segundos desde que empezó la carga.",
    noTestsTitle: "No hay corridas grabadas",
    noTestsBody: "Se leen de docs/tests: arranca Aegis o el replay desde el repositorio.",
    calibrationTitle: "Calibración: cuánto aguanta un pod y cuánto tarda en arrancar",
    eTraffic: "Carga planificada (punteada) y demanda medida", ePods: "Pods pedidos (sólido) y listos (punteado)",
    eLatency: "P95 que vio el cliente", eFailed: "Peticiones fallidas", eRisk: "Probabilidad de no alcanzar, según Aegis",
    secondsAxis: "s desde el inicio", crossesC: "supera C",
    mFailed: "Peticiones fallidas", mDegraded: "Segundos degradado", mP95: "P95 del cliente",
    mCrosses: "El tráfico supera C", mFirstUp: "Primer pod pedido", mReady: "2º pod listo", mLead: "Adelanto (C − listo)",
    mMaxPods: "Pods máximos", mPodMinutes: "Pods-minuto", mRequests: "Peticiones", mScale: "Cambios de pods",
    runName: "Prueba {n}, {mode}, {profile}, corrida {run}", runShort: "Prueba {n}, corrida {run}",
    calText: "C = {c} req/s (corridas: {runs}). T = {t} s (pods listos en {ready} s). Medido el {at}.",
    calP95: "P95 máximo por escalón, 1 pod", calServed: "Atendidas frente a enviadas, 1 pod",
    calRun: "corrida {n}", calSent: "enviadas", sentAxis: "req/s enviadas",
    langButton: "EN",
  },
  en: {
    tabLive: "Live", tabExperiments: "Experiments", all: "All",
    waitingTitle: "Waiting for the first Aegis cycle",
    waitingBody: "Aegis serves this page. Start it live or replay a recorded run:",
    versusTitle: "Aegis against the HPA alone, same load",
    versusLead: "With this same load, the HPA alone let <b>{hpa} %</b> of requests fail; with Aegis, <b>{aegis} %</b>. Aegis asked for the 2nd pod <b>{gain} s earlier</b>.",
    vsAegis: "Aegis (this run)", vsHpa: "HPA alone (median run)",
    vsAsk: "Asks for the 2nd pod", vsFailed: "Failed requests", vsSlow: "Seconds with the service slow", vsCost: "Cost (pod-minutes)",
    vsBefore: "{s} s, {d} s before one pod is exceeded", vsAfter: "{s} s, {d} s after one pod is exceeded", vsNever: "never",
    vsNote: "Final results of each run, measured by k6 on the client. HPA alone: {n} runs, failures between {min} and {max} %. In “Last minutes”, the grey line is the capacity the HPA alone had at the same moment of the load.",
    vsMissing: "This load was not run with the HPA alone. Pick test 1 (ramp) or test 4 (spike) to see the comparison.",
    lHpa: "HPA alone capacity",
    profiles: { linear: "ramp", fluctuating: "waves", spike: "spike", "ramp-045": "faster ramp", "ramp-050": "fastest ramp" },
    replayPick: "Recorded run being replayed", replayNote: "Test {n}: {desc}", replayError: "Could not switch the run: {e}",
    test1: "a ramp from 5 to 46 req/s in 2 minutes, 1 minute at the top, then down.",
    test2: "two waves of traffic (up to 28 and up to 46 req/s) with 2 minutes of low traffic after each. Aegis scales up on each wave and gives the pods back in between.",
    test4: "a jump from 5 to 41 req/s in 5 seconds, with no trend before it: it cannot be anticipated.",
    test6: "a faster ramp (0.41 req/s per second).",
    test7: "a faster ramp (0.46 req/s per second).",
    test8: "the ramp of test 1, with the HPA reading the Aegis decision through the Custom Metrics API.",
    testOther: "a saved run.",
    stateLive: "Live", stateReplay: "Replaying", stateDry: "Dry-run, not applying", stateOffline: "Aegis is not answering",
    lastCycle: "last cycle {s} s ago", speed: "at ×{v}",
    vOverflow: "The pods are not enough.", vScale: "In {h} s they would not be enough: Aegis asks for another pod.",
    vShrink: "One pod is spare: Aegis turns it off.", vNear: "The pods are enough, but close to the limit.", vWaiting: "At the limit until pod {n} is Ready.", vCalm: "The pods are comfortably enough.",
    vNoData: "No traffic data this cycle.",
    detail: "<b>{r} req/s</b> arrive. {ready} {readyWord} {serveVerb} <b>{cap} req/s</b> ({c} each). In {h} s <b>{p} req/s</b> are expected: chance of falling short, {risk}.",
    starting: " {n} more {verb} requested but not Ready yet.", startingOne: "is", startingMany: "are",
    pod: "pod", pods: "pods", podN: "Pod {n}", serveOne: "serves", serveMany: "serve",
    tankLoad: "at {v} %", tankStarting: "not Ready yet", tankOff: "off",
    tankOverflow: "{v} req/s not served",
    tankKey: "Water is the traffic each pod receives (Traefik splits it evenly). The amber line is the level expected in {h} s. A dashed pod is not Ready: it is starting, or so saturated that it misses its health check.",
    historyTitle: "Last minutes", decisionsTitle: "What Aegis did",
    lTraffic: "traffic", lCapacity: "capacity (ready pods)", lForecast: "in {h} s",
    upEvent: "Asked for pod {n}", downEvent: "Turned off pod {n}",
    upWhy: "In {h} s it expected {p} req/s and {n} {podsWord} {serveVerb} {cap}. Chance of falling short: {risk}.",
    downWhy: "Traffic dropped: with {n} {podsWord} the chance of falling short had stayed under {down} for 60 s, so one was spare.",
    noDecisions: "Nothing changed yet: Aegis holds the pods.",
    markUp: "+1 pod", markDown: "−1 pod",
    techTitle: "How Aegis decides", techHint: "The formula and the signals it uses every cycle",
    fDemand: "traffic arriving", fTrend: "how much it rises per second", fHorizon: "time a pod needs to be ready (T + delay)",
    fForecast: "expected traffic", fCapacity: "what the requested pods serve", fError: "how wrong the projection is",
    fRisk: "chance of falling short", fRule: "It asks for a pod above {up}. It turns one off if, with one pod less, it stays under {down} for 60 s.",
    chartForecast: "How well it predicts", chartForecastNote: "Each projection drawn at the moment it was made for, next to the traffic that actually arrived.",
    chartRisk: "Chance of falling short in 35 s", chartRiskNote: "Above the 70 % line Aegis asks for a pod. The grey line is the same with one pod less: if it stays under 30 % for 60 s, one is turned off.",
    chartPods: "Pods", chartPodsNote: "Requested by Aegis, already ready, and what the HPA does.",
    chartLatency: "Slowness (P95)", chartLatencyNote: "95 % of requests take less than this. Above 1 s the service counts as slow.",
    chartSigma: "Projection error (σ)", chartSigmaNote: "How far it has recently been too low. More error, more caution.",
    chartSlope: "Trend (m)", chartSlopeNote: "How many req/s the traffic rises or falls per second.",
    sDemand: "arrived", sProjected: "projected", sRisk: "with the requested pods", sRiskLess: "with one pod less",
    sTarget: "requested", sReady: "ready", sHpa: "HPA desired", sP95: "P95", sSigma: "σ", sSlope: "m",
    ruleUp: "asks at {v}", ruleDown: "turns off below {v}", ruleL: "slow above {v} s",
    paramsTitle: "Parameters", cyclesTitle: "Every cycle as a table",
    pC: "Capacity of one pod", pT: "Pod startup", pLag: "Measurement delay", pWindow: "Trend window",
    pL: "Slowness threshold", pTd: "Sustained time", pUp: "Threshold to ask", pDown: "Threshold to turn off",
    pDownWait: "Wait to turn off", pRange: "Pod range", pMode: "How it acts", pCalibrated: "Calibrated",
    modeMin: "writes minReplicas", modeMetric: "publishes a metric",
    colTime: "time", colAction: "pods", colReason: "reason",
    experimentsTitle: "Recorded runs",
    runHint: "Tick up to 3 to see them on one axis, in seconds since the load started.",
    noTestsTitle: "No recorded runs",
    noTestsBody: "They are read from docs/tests: start Aegis or the replay from the repository.",
    calibrationTitle: "Calibration: how much one pod serves and how long it takes to start",
    eTraffic: "Planned load (dotted) and measured demand", ePods: "Pods requested (solid) and ready (dotted)",
    eLatency: "P95 seen by the client", eFailed: "Failed requests", eRisk: "Chance of falling short, per Aegis",
    secondsAxis: "s since the start", crossesC: "passes C",
    mFailed: "Failed requests", mDegraded: "Seconds degraded", mP95: "Client P95",
    mCrosses: "Traffic passes C", mFirstUp: "First pod requested", mReady: "2nd pod Ready", mLead: "Lead (C − Ready)",
    mMaxPods: "Max pods", mPodMinutes: "Pod-minutes", mRequests: "Requests", mScale: "Pod changes",
    runName: "Test {n}, {mode}, {profile}, run {run}", runShort: "Test {n}, run {run}",
    calText: "C = {c} req/s (runs: {runs}). T = {t} s (pods Ready in {ready} s). Measured {at}.",
    calP95: "Highest P95 per step, 1 pod", calServed: "Served vs sent, 1 pod",
    calRun: "run {n}", calSent: "sent", sentAxis: "req/s sent",
    langButton: "ES",
  },
};

let lang = new URLSearchParams(location.search).get("lang") || readPreference("aegis-lang") || (navigator.language || "es").slice(0, 2);
if (!TEXT[lang]) lang = "es";

function t(key, values) {
  let text = TEXT[lang][key] ?? TEXT.es[key] ?? key;
  for (const [name, value] of Object.entries(values || {})) text = text.replace("{" + name + "}", value);
  return text;
}

function readPreference(key) {
  try { return localStorage.getItem(key); } catch { return null; }
}

function writePreference(key, value) {
  try { localStorage.setItem(key, value); } catch { /* storage blocked: keep it for this page only */ }
}

function el(tag, className, parent, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = text;
  if (parent) parent.appendChild(node);
  return node;
}

const num = (value, decimals = 1) => (value === null || value === undefined || Number.isNaN(value) ? "–" : Number(value).toFixed(decimals));
const pct = (value, decimals = 1) => (value === null || value === undefined ? "–" : (value * 100).toFixed(decimals) + "%");
const clock = (unix) => new Date(unix * 1000).toLocaleTimeString(lang, { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
const clockShort = (unix) => new Date(unix * 1000).toLocaleTimeString(lang, { hour: "2-digit", minute: "2-digit", hour12: false });

// +1.23 / −1.23: the sign always shown, for slopes and z.
function signed(value, decimals) {
  if (value === null || value === undefined) return "–";
  return (value >= 0 ? "+" : "−") + Math.abs(value).toFixed(decimals);
}

/* ---------------------------------------------------------------- live view */

const live = {
  meta: null,
  records: [],
  actions: null,
  session: null,
  windowSeconds: Number(readPreference("aegis-window") || 900),
  lastTime: null,
  online: true,
  charts: {},
};

function horizonOf(meta) {
  return meta.startup_time_seconds + meta.metric_lag_seconds;
}

function buildLiveCharts() {
  const group = new ChartGroup();
  const timeOptions = { xFormat: (v, long, step) => (long || step < 60 ? clock(v) : clockShort(v)), timeTicks: true, stepTail: 5 };
  const hero = document.getElementById("hero-chart");
  hero.replaceChildren();
  live.charts.traffic = group.add(new LineChart(hero, Object.assign({
    unit: "req/s", height: 300, marginRight: 150, yFormat: (v) => num(v, 0), valueFormat: (v) => num(v, 1) + " req/s",
    series: [
      { key: "rps", label: t("lTraffic"), endLabel: t("lTraffic"), color: "var(--water)", fill: true, width: 2.5, connect: true },
      { key: "capacity", label: t("lCapacity"), endLabel: t("lCapacity"), color: "var(--ink)", step: true, width: 3, connect: true },
      { key: "hpaCapacity", label: t("lHpa"), endLabel: t("lHpa"), color: "var(--quiet)", step: true, dash: "6 4", width: 2, connect: true },
    ],
  }, timeOptions)));

  const container = document.getElementById("live-charts");
  container.replaceChildren();
  const add = (key, options) => {
    live.charts[key] = group.add(new LineChart(container, Object.assign({}, timeOptions, options)));
    return live.charts[key];
  };
  add("forecast", { title: t("chartForecast"), note: t("chartForecastNote"), unit: "req/s", height: 200,
    yFormat: (v) => num(v, 0), valueFormat: (v) => num(v, 1),
    series: [
      { key: "rps", label: t("sDemand"), color: "var(--water)", width: 2.5, connect: true },
      { key: "projected", label: t("sProjected"), color: "var(--forecast)", dash: "1 5", width: 2.5, connect: true },
    ] }).root.classList.add("wide");
  add("risk", { title: t("chartRisk"), note: t("chartRiskNote"), unit: "%", height: 170, yMax: 100,
    yFormat: (v) => num(v, 0) + "%", valueFormat: (v) => num(v, 1) + "%",
    series: [
      { key: "risk", label: t("sRisk"), color: "var(--ink)", width: 2.5 },
      { key: "riskLess", label: t("sRiskLess"), color: "var(--quiet)", dash: "4 4", width: 1.5 },
    ] }).root.classList.add("wide");
  add("pods", { title: t("chartPods"), note: t("chartPodsNote"), height: 130, yMaxAtLeast: 3,
    yFormat: (v) => (Number.isInteger(v) ? String(v) : ""), valueFormat: (v) => num(v, 0),
    series: [
      { key: "target", label: t("sTarget"), color: "var(--ink)", step: true, width: 3 },
      { key: "ready", label: t("sReady"), color: "var(--water)", step: true },
      { key: "hpaDesired", label: t("sHpa"), color: "var(--quiet)", step: true, dash: "2 3", width: 1.5 },
    ] });
  add("latency", { title: t("chartLatency"), note: t("chartLatencyNote"), unit: "s", height: 130, yMaxAtLeast: 0.5,
    yFormat: (v) => num(v, 1), valueFormat: (v) => num(v, 3) + " s",
    series: [{ key: "p95", label: t("sP95"), color: "var(--alarm)" }] });
  add("sigma", { title: t("chartSigma"), note: t("chartSigmaNote"), unit: "req/s", height: 120,
    yFormat: (v) => num(v, 1), valueFormat: (v) => num(v, 2), series: [{ key: "sigma", label: t("sSigma"), color: "var(--forecast)" }] });
  add("slope", { title: t("chartSlope"), note: t("chartSlopeNote"), unit: "req/s²", height: 120, yMin: null, yMaxAtLeast: 0.1,
    yFormat: (v) => num(v, 2), valueFormat: (v) => signed(v, 3), series: [{ key: "slope", label: t("sSlope"), color: "var(--water)" }] });
}

async function poll() {
  try {
    const query = live.lastTime === null ? "" : "?since=" + live.lastTime;
    const response = await fetch("api/state" + query, { cache: "no-store" });
    if (!response.ok) throw new Error(response.status);
    const body = await response.json();
    if (body.meta.session !== live.session) {
      live.session = body.meta.session;
      live.records = [];
      live.lastTime = null;
      if (query) return poll();
    }
    live.meta = body.meta;
    live.actions = body.actions;
    if (body.records.length) {
      live.records.push(...body.records);
      if (live.records.length > 4000) live.records.splice(0, live.records.length - 4000);
      live.lastTime = live.records[live.records.length - 1].time;
    }
    live.online = true;
  } catch (error) {
    live.online = false;
  }
  renderLive();
}

function renderStatus() {
  const line = document.getElementById("source");
  line.replaceChildren();
  const meta = live.meta;
  const mode = !live.online || !meta ? "offline" : meta.mode;
  const labels = { live: t("stateLive"), replay: t("stateReplay"), "dry-run": t("stateDry"), offline: t("stateOffline") };
  el("span", "state " + mode, line, labels[mode]);
  if (mode === "offline") return;
  const parts = [];
  if (mode === "replay") {
    parts.push((meta.source || "").replace("-aegis.ndjson", ""));
    if (meta.speed !== 1) parts.push(t("speed", { v: meta.speed }));
  } else {
    parts.push(meta.namespace + "/" + meta.deployment);
    const last = live.records[live.records.length - 1];
    if (last) parts.push(t("lastCycle", { s: Math.max(0, Math.round(Date.now() / 1000 - last.time)) }));
  }
  line.appendChild(document.createTextNode(" " + parts.join(" ")));
}

function columns(records, meta) {
  const C = meta.pod_capacity_rps;
  const cols = { risk: [], riskLess: [], target: [], ready: [], hpaDesired: [], p95: [], sigma: [], slope: [] };
  const x = [];
  for (const r of records) {
    x.push(r.time);
    cols.risk.push(r.risk === null ? null : r.risk * 100);
    cols.riskLess.push(r.risk_one_less === null || r.risk_one_less === undefined ? null : r.risk_one_less * 100);
    cols.target.push(r.target);
    cols.ready.push(r.replicas_ready);
    cols.hpaDesired.push(r.hpa_desired ?? null);
    cols.p95.push(r.p95_s);
    cols.sigma.push(r.sigma_rps);
    cols.slope.push(r.slope);
  }
  const traffic = { rps: records.map((r) => r.rps),
    capacity: records.map((r) => (r.replicas_ready === null ? null : C * r.replicas_ready)), hpaCapacity: records.map(() => null) };
  // Same moment of the load in the HPA-only run: seconds since its k6 start, rows every 5 s.
  const pair = comparison(meta);
  if (pair && pair.rows) {
    const bySecond = new Map(pair.rows.map((row) => [Math.round(row.seconds / 5) * 5, row]));
    traffic.hpaCapacity = records.map((r) => {
      const row = bySecond.get(Math.round((r.time - pair.k6Start) / 5) * 5);
      return row && row.ready !== null && row.ready !== "" ? C * Number(row.ready) : null;
    });
  }
  // Forecast check: each projection at the moment it was made for (T + lag later).
  const horizon = horizonOf(meta);
  const byTime = new Map(records.map((r) => [r.time, { rps: r.rps, projected: null }]));
  for (const r of records) {
    if (r.projected_rps === null) continue;
    const at = r.time + horizon;
    if (!byTime.has(at)) byTime.set(at, { rps: null, projected: null });
    byTime.get(at).projected = r.projected_rps;
  }
  const forecastX = [...byTime.keys()].sort((a, b) => a - b);
  const forecast = { rps: forecastX.map((k) => byTime.get(k).rps), projected: forecastX.map((k) => byTime.get(k).projected) };
  return { x, cols, traffic, forecastX, forecast };
}

function renderLive() {
  renderStatus();
  const meta = live.meta;
  const records = live.records;
  const empty = !meta || !records.length;
  document.getElementById("empty-live").hidden = !empty;
  document.getElementById("tab-live").classList.toggle("is-empty", empty);
  if (empty) return;
  const last = records[records.length - 1];
  const first = records[0];
  const horizon = horizonOf(meta);
  const start = live.windowSeconds ? Math.max(first.time, last.time - live.windowSeconds) : first.time;
  const domain = [Math.min(start, last.time - 60), last.time + 5];
  const { x, cols, traffic, forecastX, forecast } = columns(records, meta);
  const markers = [];
  for (const r of records) {
    if (r.action === "scale_up") markers.push({ x: r.time, kind: "up", label: t("markUp") });
    if (r.action === "scale_down") markers.push({ x: r.time, kind: "down", label: t("markDown") });
  }
  live.charts.traffic.setData({
    x, columns: traffic, domain: [domain[0], last.time + horizon + 2], markers, now: last.time,
    zones: [{ x0: last.time, x1: last.time + horizon }],
    segments: [{ x0: last.time, y0: last.rps, x1: last.time + horizon, y1: last.projected_rps === null ? null : Math.max(0, last.projected_rps), color: "var(--forecast)",
      label: last.projected_rps === null ? "" : t("lForecast", { h: num(horizon, 0) }) + ": " + num(Math.max(0, last.projected_rps), 0) }],
  });
  const upPct = meta.scale_up_threshold * 100;
  const downPct = meta.scale_down_threshold * 100;
  const base = { x, columns: cols, domain, markers };
  live.charts.forecast.setData({ x: forecastX, columns: forecast, domain, markers });
  live.charts.risk.setData(Object.assign({}, base, {
    rules: [{ y: upPct, label: t("ruleUp", { v: num(upPct, 0) + "%" }) }, { y: downPct, label: t("ruleDown", { v: num(downPct, 0) + "%" }) }],
    bands: [{ y0: upPct, y1: 100, color: "var(--band-up)" }, { y0: 0, y1: downPct, color: "var(--band-down)" }],
  }));
  live.charts.pods.setData(Object.assign({}, base, { rules: [] }));
  live.charts.latency.setData(Object.assign({}, base,
    { rules: [{ y: meta.p95_threshold_seconds, label: t("ruleL", { v: meta.p95_threshold_seconds }) }] }));
  live.charts.sigma.setData(Object.assign({}, base, { markers: [] }));
  live.charts.slope.setData(Object.assign({}, base, { markers: [], rules: [{ y: 0, label: "" }] }));
  renderReplayNote(meta);
  renderVersus(meta);
  renderVerdict(last, meta);
  renderTanks(last, meta);
  renderEquation(last, meta);
  renderDecisions(records, meta);
  renderParams(meta);
  renderCycles(records.filter((r) => r.time >= start));
}

const podsWord = (n) => (n === 1 ? t("pod") : t("pods"));
const serveVerb = (n) => (n === 1 ? t("serveOne") : t("serveMany"));

// Recorded runs that can be replayed: the ones with an Aegis log (not the HPA-only tests).
const replay = { runs: null, all: null, loading: false, hpaRows: {} };

async function loadReplayRuns() {
  if (replay.runs || replay.loading) return;
  replay.loading = true;
  try {
    const catalog = await (await fetch("api/tests", { cache: "no-store" })).json();
    replay.all = [];
    for (const test of catalog.tests) for (const summary of test.runs) replay.all.push({ test: test.name, summary });
    replay.runs = replay.all.filter((entry) => entry.summary.mode !== "hpa");
  } catch {
    replay.runs = [];
    replay.all = [];
  }
  replay.loading = false;
  fillReplayPicker();
}

function fillReplayPicker() {
  const select = document.getElementById("replay-run");
  if (!replay.runs || !live.meta) return;
  const current = (live.meta.source || "").replace("-aegis.ndjson", "");
  select.replaceChildren();
  for (const entry of replay.runs) {
    const option = el("option", "", select, runLabel(entry));
    option.value = entry.test + "/run-" + entry.summary.run;
    option.selected = option.value === current;
  }
}

async function switchReplay(value) {
  const [test, run] = value.split("/run-");
  const response = await fetch("api/replay", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ test, run: Number(run) }) });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    document.getElementById("replay-note").textContent = t("replayError", { e: body.error || response.status });
    return;
  }
  live.records = [];
  live.lastTime = null;
  poll();
}

// The Aegis run being replayed and the HPA-only runs with the same load (median by failed requests).
function comparison(meta) {
  if (meta.mode !== "replay" || !replay.all) return null;
  const current = (meta.source || "").replace("-aegis.ndjson", "");
  const aegis = replay.all.find((e) => e.test + "/run-" + e.summary.run === current);
  if (!aegis) return null;
  const hpa = replay.all.filter((e) => e.summary.mode === "hpa" && e.summary.profile === aegis.summary.profile)
    .sort((a, b) => a.summary.failed_percent - b.summary.failed_percent);
  const median = hpa.length ? hpa[Math.floor((hpa.length - 1) / 2)] : null;
  if (median && !replay.hpaRows[median.test + median.summary.run]) {
    replay.hpaRows[median.test + median.summary.run] = "loading";
    fetch("api/tests/" + median.test + "/" + median.summary.run, { cache: "no-store" }).then((r) => r.json())
      .then((run) => { replay.hpaRows[median.test + median.summary.run] = run.rows; renderLive(); });
  }
  const rows = median ? replay.hpaRows[median.test + median.summary.run] : null;
  return { aegis, hpa, median, rows: Array.isArray(rows) ? rows : null,
    k6Start: Date.parse(aegis.summary.date_utc + "T" + aegis.summary.k6_start_utc + "Z") / 1000 };
}

function renderVersus(meta) {
  const box = document.getElementById("versus");
  const pair = comparison(meta);
  box.hidden = !pair;
  if (!pair) return;
  const lead = document.getElementById("versus-lead");
  const table = document.getElementById("versus-table");
  const note = document.getElementById("versus-note");
  table.replaceChildren();
  if (!pair.median) {
    lead.textContent = "";
    note.textContent = t("vsMissing");
    return;
  }
  const a = pair.aegis.summary;
  const h = pair.median.summary;
  lead.innerHTML = t("versusLead", { hpa: num(h.failed_percent, 1), aegis: num(a.failed_percent, 1),
    gain: num((h.first_scale_up_s ?? 0) - (a.first_scale_up_s ?? 0), 0) });
  const ask = (s) => {
    if (s.first_scale_up_s === null || s.first_scale_up_s === undefined) return t("vsNever");
    const delta = s.crosses_c_s - s.first_scale_up_s;
    return t(delta >= 0 ? "vsBefore" : "vsAfter", { s: num(s.first_scale_up_s, 0), d: num(Math.abs(delta), 0) });
  };
  const head = el("tr", "", el("thead", "", table));
  el("th", "", head, "");
  el("th", "aegis", head, t("vsAegis"));
  el("th", "hpa", head, t("vsHpa"));
  const body = el("tbody", "", table);
  const rows = [
    [t("vsAsk"), ask(a), ask(h), null],
    [t("vsFailed"), num(a.failed_percent, 1) + " %", num(h.failed_percent, 1) + " %", a.failed_percent < h.failed_percent],
    [t("vsSlow"), num(a.degraded_seconds, 0) + " s", num(h.degraded_seconds, 0) + " s", a.degraded_seconds < h.degraded_seconds],
    [t("vsCost"), num(a.pod_minutes, 1), num(h.pod_minutes, 1), null],
  ];
  for (const [label, av, hv, aegisBetter] of rows) {
    const row = el("tr", "", body);
    el("td", "", row, label);
    el("td", "aegis" + (aegisBetter === true ? " better" : ""), row, av);
    el("td", "hpa" + (aegisBetter === false ? " better" : ""), row, hv);
  }
  const failures = pair.hpa.map((e) => e.summary.failed_percent);
  note.textContent = t("vsNote", { n: pair.hpa.length, min: num(Math.min(...failures), 1), max: num(Math.max(...failures), 1) });
}

function renderReplayNote(meta) {
  const bar = document.getElementById("replay-bar");
  bar.hidden = meta.mode !== "replay";
  if (bar.hidden) return;
  loadReplayRuns();
  const select = document.getElementById("replay-run");
  const current = (meta.source || "").replace("-aegis.ndjson", "");
  if (replay.runs && select.value !== current && document.activeElement !== select) fillReplayPicker();
  const match = (meta.source || "").match(/^test(\d+)-/);
  const n = match ? match[1] : "";
  document.getElementById("replay-note").textContent =
    t("replayNote", { n, desc: TEXT[lang]["test" + n] ? t("test" + n) : t("testOther") });
}

function renderVerdict(r, meta) {
  const title = document.getElementById("verdict");
  const detail = document.getElementById("verdict-detail");
  const C = meta.pod_capacity_rps;
  const ready = r.replicas_ready ?? r.target;
  const load = r.rps === null || !ready ? 0 : r.rps / (C * ready);
  let kind = "calm";
  if (load > 1) kind = "overflow";
  else if (r.action === "scale_up") kind = "scale";
  else if (r.action === "scale_down") kind = "shrink";
  else if (r.target > ready && load >= 0.7) kind = "waiting";
  else if (load >= 0.8 || (r.risk !== null && r.risk >= meta.scale_down_threshold)) kind = "near";
  const keys = { overflow: "vOverflow", scale: "vScale", shrink: "vShrink", near: "vNear", waiting: "vWaiting", calm: "vCalm" };
  title.className = kind;
  title.textContent = t(keys[kind], { h: num(horizonOf(meta), 0), n: ready + 1 });
  if (r.rps === null || r.projected_rps === null) {
    detail.textContent = t("vNoData");
    return;
  }
  let text = t("detail", { r: num(r.rps, 1), ready, readyWord: podsWord(ready), serveVerb: serveVerb(ready), cap: num(C * ready, 0), c: num(C, 0),
    h: num(horizonOf(meta), 0), p: num(Math.max(0, r.projected_rps), 1), risk: pct(r.risk, 0) });
  const starting = r.target - ready;
  if (starting > 0) text += t("starting", { n: starting, verb: starting === 1 ? t("startingOne") : t("startingMany") });
  detail.innerHTML = text;
}

// One tank per pod up to maxReplicas. Traefik splits the traffic evenly, so every Ready pod fills to the same level.
function renderTanks(r, meta) {
  const box = document.getElementById("tanks");
  box.replaceChildren();
  const C = meta.pod_capacity_rps;
  const ready = r.replicas_ready ?? r.target;
  const load = r.rps === null || !ready ? null : r.rps / (C * ready);
  const forecastLoad = r.projected_rps === null ? null : Math.max(0, r.projected_rps) / (C * Math.max(1, r.target));
  for (let i = 0; i < meta.max_replicas; i++) {
    const state = i < ready ? "ready" : i < r.target ? "starting" : "off";
    const tank = el("div", "tank " + state, box);
    const vessel = el("div", "vessel", tank);
    if (state === "ready" && load !== null) {
      const water = el("div", "water" + (load > 1 ? " full" : ""), vessel);
      water.style.height = Math.min(100, load * 100) + "%";
    }
    if (state !== "off" && forecastLoad !== null) {
      const mark = el("div", "forecast-mark" + (forecastLoad > 1 ? " over" : ""), vessel);
      mark.style.bottom = Math.min(100, forecastLoad * 100) + "%";
    }
    el("div", "tank-name", tank, t("podN", { n: i + 1 }));
    let status = t("tankOff");
    if (state === "starting") status = t("tankStarting");
    if (state === "ready") status = load === null ? "–" : t("tankLoad", { v: num(load * 100, 0) });
    el("div", "tank-status", tank, status);
  }
  const overflow = r.rps === null ? 0 : r.rps - C * ready;
  if (overflow > 0.5) el("div", "overflow", box, t("tankOverflow", { v: num(overflow, 1) }));
  document.getElementById("tank-key").textContent = t("tankKey", { h: num(horizonOf(meta), 0) });
}

function renderEquation(r, meta) {
  const box = document.getElementById("equation");
  box.replaceChildren();
  const C = meta.pod_capacity_rps;
  const N = r.previous_target;
  const line = el("p", "formula-line", box);
  const term = (symbol, value, meaning, kind) => {
    const node = el("span", "term" + (kind ? " " + kind : ""), line);
    el("i", "", node, symbol);
    el("b", "", node, value);
    el("small", "", node, meaning);
  };
  const op = (text) => el("span", "op", line, text);
  term("r", num(r.rps, 1), t("fDemand"), "t-water");
  op("+");
  term("m", signed(r.slope, 2), t("fTrend"));
  op("×");
  term("T + lag", num(horizonOf(meta), 0) + " s", t("fHorizon"));
  op("=");
  term("p", num(r.projected_rps === null ? null : Math.max(0, r.projected_rps), 1), t("fForecast"), "t-forecast");
  const second = el("p", "formula-line", box);
  const term2 = (symbol, value, meaning, kind) => {
    const node = el("span", "term" + (kind ? " " + kind : ""), second);
    el("i", "", node, symbol);
    el("b", "", node, value);
    el("small", "", node, meaning);
  };
  term2("C · N", num(C, 0) + " × " + N + " = " + num(C * N, 0), t("fCapacity"));
  el("span", "op", second, "·");
  term2("σ", num(r.sigma_rps, 1), t("fError"));
  el("span", "op", second, "→");
  term2("Φ((p − C·N) / σ)", pct(r.risk), t("fRisk"), r.risk !== null && r.risk >= meta.scale_up_threshold ? "t-alarm" : "");
  el("p", "formula-rule", box, t("fRule", { up: pct(meta.scale_up_threshold, 0), down: pct(meta.scale_down_threshold, 0) }));
}

function renderDecisions(records, meta) {
  const list = document.getElementById("decisions");
  list.replaceChildren();
  const changes = records.filter((r) => r.action !== "hold").slice(-40).reverse();
  if (!changes.length) el("li", "empty-note", list, t("noDecisions"));
  const C = meta.pod_capacity_rps;
  for (const r of changes) {
    const up = r.action === "scale_up";
    const li = el("li", up ? "up" : "down", list);
    const head = el("div", "log-head", li);
    el("span", "what", head, up ? t("upEvent", { n: r.target }) : t("downEvent", { n: r.previous_target }));
    el("span", "when", head, clock(r.time));
    const why = up
      ? t("upWhy", { h: num(horizonOf(meta), 0), p: num(r.projected_rps, 0), n: r.previous_target,
        podsWord: podsWord(r.previous_target), serveVerb: serveVerb(r.previous_target), cap: num(C * r.previous_target, 0), risk: pct(r.risk, 0) })
      : t("downWhy", { down: pct(meta.scale_down_threshold, 0), n: r.target, podsWord: podsWord(r.target) });
    el("p", "why", li, why);
  }
}

function renderParams(meta) {
  const list = document.getElementById("params");
  list.replaceChildren();
  const rows = [
    [t("pC"), "C", num(meta.pod_capacity_rps, 0) + " req/s"],
    [t("pT"), "T", num(meta.startup_time_seconds, 0) + " s"],
    [t("pLag"), "lag", meta.metric_lag_seconds + " s"],
    [t("pWindow"), "", meta.projection_window_seconds + " s"],
    [t("pL"), "L", meta.p95_threshold_seconds + " s"],
    [t("pTd"), "T_d", meta.sustained_seconds + " s"],
    [t("pUp"), "", pct(meta.scale_up_threshold, 0)],
    [t("pDown"), "", pct(meta.scale_down_threshold, 0)],
    [t("pDownWait"), "", meta.scale_down_sustained_seconds + " s"],
    [t("pRange"), "", meta.min_replicas + "–" + meta.max_replicas],
    [t("pMode"), "", meta.actuator_mode === "metric" ? t("modeMetric") : t("modeMin")],
  ];
  if (meta.calibrated_at) rows.push([t("pCalibrated"), "", meta.calibrated_at.replace("T", " ").replace("Z", " UTC")]);
  for (const [label, symbol, value] of rows) {
    const dt = el("dt", "", list, label);
    if (symbol) el("i", "", dt, symbol);
    el("dd", "", list, value);
  }
}

function renderCycles(records) {
  const table = document.getElementById("cycles-table");
  if (!table.closest("details").open) return;
  table.replaceChildren();
  const head = el("tr", "", el("thead", "", table));
  const keys = [[t("colTime"), (r) => clock(r.time)], ["r", (r) => num(r.rps, 2)], ["m", (r) => signed(r.slope, 3)],
    ["p", (r) => num(r.projected_rps, 2)], ["σ", (r) => num(r.sigma_rps, 2)], ["C·N", (r) => num(r.capacity_rps, 0)],
    ["Φ", (r) => pct(r.risk)], ["P95", (r) => num(r.p95_s, 3)], [t("sReady"), (r) => r.replicas_ready ?? "–"],
    [t("colAction"), (r) => r.previous_target + "→" + r.target], [t("colReason"), (r) => r.reason]];
  for (const [label] of keys) el("th", "", head, label);
  const body = el("tbody", "", table);
  for (const r of records.slice(-120).reverse()) {
    const row = el("tr", "", body);
    for (const [, value] of keys) el("td", "", row, String(value(r)));
  }
}

/* --------------------------------------------------------- experiments view */

const experiments = { loaded: false, catalog: null, runs: [], selected: [], cache: {}, charts: {} };

function runId(test, run) {
  return test + "/" + run;
}

function runLabel(entry, short) {
  const match = entry.test.match(/^test(\d+)/);
  const mode = { hpa: "HPA", metric: "Aegis (metric)" }[entry.summary.mode] || "Aegis";
  const profile = TEXT[lang].profiles[entry.summary.profile] || entry.summary.profile;
  return t(short ? "runShort" : "runName", { n: match ? match[1] : entry.test, mode, profile,
    run: entry.summary.run });
}

async function loadExperiments() {
  if (experiments.loaded) return;
  experiments.loaded = true;
  try {
    const response = await fetch("api/tests", { cache: "no-store" });
    experiments.catalog = await response.json();
  } catch {
    experiments.catalog = { tests: [], calibration: null };
  }
  experiments.runs = [];
  for (const test of experiments.catalog.tests) {
    for (const summary of test.runs) experiments.runs.push({ id: runId(test.name, summary.run), test: test.name, summary });
  }
  experiments.runs.forEach((entry, index) => { entry.color = RUN_COLORS[index % RUN_COLORS.length]; });
  document.getElementById("empty-experiments").hidden = experiments.runs.length > 0;
  // The median runs of the main comparison: test 1 run 4 (Aegis) and test 3 run 1 (HPA only).
  const preferred = experiments.runs.filter((e) => (/^test1-/.test(e.test) && e.summary.run === 4)
    || (/^test3-/.test(e.test) && e.summary.run === 1)).map((e) => e.id);
  experiments.selected = preferred.length ? preferred : experiments.runs.slice(0, 2).map((e) => e.id);
  buildRunPicker();
  buildExperimentCharts();
  renderCalibration();
  await renderExperiments();
}

function buildRunPicker() {
  const picker = document.getElementById("run-picker");
  picker.replaceChildren();
  for (const entry of experiments.runs) {
    const label = el("label", "run", picker);
    const input = el("input", "", label);
    input.type = "checkbox";
    input.checked = experiments.selected.includes(entry.id);
    input.addEventListener("change", () => {
      if (input.checked) {
        experiments.selected.push(entry.id);
        if (experiments.selected.length > MAX_RUNS) {
          const dropped = experiments.selected.shift();
          for (const box of picker.querySelectorAll("input")) if (box.dataset.id === dropped) box.checked = false;
        }
      } else {
        experiments.selected = experiments.selected.filter((id) => id !== entry.id);
      }
      renderExperiments();
    });
    input.dataset.id = entry.id;
    const swatch = el("span", "swatch", label);
    swatch.style.background = entry.color;
    el("span", "", label, runLabel(entry));
  }
}

function buildExperimentCharts() {
  const container = document.getElementById("experiment-charts");
  container.replaceChildren();
  const group = new ChartGroup();
  const options = { xFormat: (v, long) => (long ? Math.round(v) + " " + t("secondsAxis") : Math.round(v) + " s"), timeTicks: true };
  const add = (key, extra) => { experiments.charts[key] = group.add(new LineChart(container, Object.assign({}, options, extra))); };
  add("traffic", { title: t("eTraffic"), unit: "req/s", height: 210, yFormat: (v) => num(v, 0), valueFormat: (v) => num(v, 1) });
  add("pods", { title: t("ePods"), height: 150, yMaxAtLeast: 3, yFormat: (v) => (Number.isInteger(v) ? String(v) : ""), valueFormat: (v) => num(v, 0) });
  add("latency", { title: t("eLatency"), unit: "s", height: 170, yFormat: (v) => num(v, 1), valueFormat: (v) => num(v, 3) + " s" });
  add("failed", { title: t("eFailed"), unit: "%", height: 150, yMaxAtLeast: 5, yCap: 100, yFormat: (v) => num(v, 0) + "%", valueFormat: (v) => num(v, 2) + "%" });
  add("risk", { title: t("eRisk"), unit: "%", height: 150, yMax: 100, yFormat: (v) => num(v, 0) + "%", valueFormat: (v) => num(v, 1) + "%" });
  experiments.charts.risk.root.classList.add("wide");
}

async function fetchRun(id) {
  if (!experiments.cache[id]) {
    const response = await fetch("api/tests/" + id, { cache: "no-store" });
    experiments.cache[id] = await response.json();
  }
  return experiments.cache[id];
}

async function renderExperiments() {
  const entries = experiments.runs.filter((e) => experiments.selected.includes(e.id));
  const data = await Promise.all(entries.map((e) => fetchRun(e.id)));
  renderSummary(entries);
  // One x axis (seconds since k6 started), aligned to the nearest 5 s.
  const align = (seconds) => Math.round(seconds / 5) * 5;
  const xsSet = new Set();
  for (const run of data) for (const row of run.rows) xsSet.add(align(row.seconds));
  const x = [...xsSet].sort((a, b) => a - b);
  const cols = {};
  const seriesFor = { traffic: [], pods: [], latency: [], failed: [], risk: [] };
  entries.forEach((entry, i) => {
    const byX = new Map(data[i].rows.map((row) => [align(row.seconds), row]));
    const pick = (fn) => x.map((s) => (byX.has(s) ? fn(byX.get(s)) : null));
    const id = "r" + i;
    cols[id + "planned"] = pick((r) => r.planned_rps);
    cols[id + "demand"] = pick((r) => r.demand_rps);
    cols[id + "requested"] = pick((r) => r.requested);
    cols[id + "ready"] = pick((r) => r.ready);
    cols[id + "p95"] = pick((r) => r.client_p95_s);
    cols[id + "failed"] = pick((r) => (r.client_failed_ratio === null ? null : r.client_failed_ratio * 100));
    cols[id + "risk"] = pick((r) => (r.aegis_risk === null ? null : r.aegis_risk * 100));
    const name = runLabel(entry, true);
    seriesFor.traffic.push({ key: id + "demand", label: name, color: entry.color },
      { key: id + "planned", label: name + " (plan)", color: entry.color, dash: "2 3", width: 1.5, hideInLegend: true });
    seriesFor.pods.push({ key: id + "requested", label: name, color: entry.color, step: true, width: 2.5 },
      { key: id + "ready", label: name + " (" + t("sReady") + ")", color: entry.color, step: true, dash: "2 3", width: 1.5, hideInLegend: true });
    seriesFor.latency.push({ key: id + "p95", label: name, color: entry.color });
    seriesFor.failed.push({ key: id + "failed", label: name, color: entry.color });
    if (entry.summary.mode !== "hpa") seriesFor.risk.push({ key: id + "risk", label: name, color: entry.color });
  });
  const domain = x.length ? [x[0], x[x.length - 1]] : [0, 1];
  const markers = [];
  const crosses = entries.length ? entries[0].summary.crosses_c_s : null;
  if (crosses !== null && crosses !== undefined) markers.push({ x: crosses, kind: "info", label: t("crossesC") });
  for (const [key, chart] of Object.entries(experiments.charts)) chart.setSeries(seriesFor[key]);
  const meta = experiments.catalog.calibration || {};
  const capacity = meta.capacity_rps ?? (entries[0] && entries[0].summary.capacity_rps);
  experiments.charts.traffic.setData({ x, columns: cols, domain, markers,
    rules: capacity ? [{ y: capacity, label: "C = " + capacity + " req/s" }] : [] });
  experiments.charts.pods.setData({ x, columns: cols, domain, markers });
  const L = (meta.degradation && meta.degradation.p95_threshold_seconds) || 1;
  experiments.charts.latency.setData({ x, columns: cols, domain, markers, rules: [{ y: L, label: t("ruleL", { v: L }) }] });
  experiments.charts.failed.setData({ x, columns: cols, domain, markers, rules: [{ y: 1, label: "1%" }] });
  experiments.charts.risk.setData({ x, columns: cols, domain, markers, rules: [{ y: 70, label: t("ruleUp", { v: "70%" }) }] });
}

function renderSummary(entries) {
  const table = document.getElementById("summary-table");
  table.replaceChildren();
  if (!entries.length) return;
  const head = el("tr", "", el("thead", "", table));
  el("th", "", head, "");
  for (const entry of entries) {
    const th = el("th", "", head);
    const swatch = el("span", "swatch", th);
    swatch.style.background = entry.color;
    th.appendChild(document.createTextNode(runLabel(entry)));
  }
  const seconds = (v) => (v === null || v === undefined ? "–" : num(v, 0) + " s");
  // lower: a smaller value is better and gets highlighted when runs are compared.
  const rows = [
    [t("mFailed"), "failed_percent", (v) => num(v, 2) + "%", "lower"],
    [t("mDegraded"), "degraded_seconds", seconds, "lower"],
    [t("mP95"), "client_p95_s", (v) => num(v, 2) + " s", "lower"],
    [t("mCrosses"), "crosses_c_s", seconds, null],
    [t("mFirstUp"), "first_scale_up_s", seconds, "lower"],
    [t("mReady"), "second_pod_ready_s", seconds, "lower"],
    [t("mLead"), "lead_s", (v) => (v === null ? "–" : signed(v, 0) + " s"), "higher"],
    [t("mMaxPods"), "max_pods", (v) => String(v), null],
    [t("mPodMinutes"), "pod_minutes", (v) => num(v, 1), "lower"],
    [t("mRequests"), "requests", (v) => String(v), null],
  ];
  const body = el("tbody", "", table);
  for (const [label, key, format, better] of rows) {
    const row = el("tr", "", body);
    el("td", "", row, label);
    const values = entries.map((e) => e.summary[key]);
    const valid = values.filter((v) => v !== null && v !== undefined);
    let best = null;
    if (better && entries.length > 1 && valid.length > 1) best = better === "lower" ? Math.min(...valid) : Math.max(...valid);
    for (const value of values) {
      const cell = el("td", value !== null && value === best ? "best" : "", row, value === null || value === undefined ? "–" : format(value));
      if (value !== null && value === best) cell.title = "✓";
    }
  }
  const row = el("tr", "", body);
  el("td", "", row, t("mScale"));
  for (const entry of entries) {
    const changes = entry.summary.scale_ups.concat(entry.summary.scale_downs).sort((a, b) => a.s - b.s)
      .map((c) => c.from + "→" + c.to + " @" + Math.round(c.s) + "s");
    el("td", "", row).appendChild(el("small", "", null, changes.join(", ") || "–"));
  }
}

function renderCalibration() {
  const calibration = experiments.catalog.calibration;
  const container = document.getElementById("calibration-charts");
  container.replaceChildren();
  if (!calibration) {
    document.getElementById("calibration-text").textContent = "–";
    return;
  }
  const runs = calibration.capacity_runs || [];
  document.getElementById("calibration-text").textContent = t("calText", {
    c: calibration.capacity_rps, runs: runs.map((r) => r.capacity_rps).join(", "), t: calibration.startup_time_seconds,
    ready: (calibration.startup_measurements || []).map((m) => m.request_to_ready_s).join(", "),
    at: (calibration.measured_at || "").replace("T", " ").replace("Z", " UTC"),
  });
  const xsSet = new Set();
  for (const run of runs) for (const s of run.steps) xsSet.add(s.target_rps);
  const x = [...xsSet].sort((a, b) => a - b);
  const cols = { sent: x.slice() };
  const p95Series = [];
  const servedSeries = [{ key: "sent", label: t("calSent"), color: "var(--quiet)", dash: "4 4", width: 1.5 }];
  runs.forEach((run, i) => {
    const byX = new Map(run.steps.map((s) => [s.target_rps, s]));
    cols["p95" + i] = x.map((v) => (byX.has(v) ? byX.get(v).p95_max_s : null));
    cols["served" + i] = x.map((v) => (byX.has(v) ? byX.get(v).measured_rps : null));
    p95Series.push({ key: "p95" + i, label: t("calRun", { n: i + 1 }) + " (C = " + run.capacity_rps + ")", color: RUN_COLORS[i], dots: true });
    servedSeries.push({ key: "served" + i, label: t("calRun", { n: i + 1 }), color: RUN_COLORS[i], dots: true });
  });
  const group = new ChartGroup();
  const xFormat = (v, long) => num(v, 0) + (long ? " " + t("sentAxis") : "");
  const markers = [{ x: calibration.capacity_rps, kind: "info", label: "C" }];
  const L = calibration.degradation ? calibration.degradation.p95_threshold_seconds : 1;
  group.add(new LineChart(container, { title: t("calP95"), unit: "s", height: 200, series: p95Series, xFormat,
    yFormat: (v) => num(v, 1), valueFormat: (v) => num(v, 3) + " s" }))
    .setData({ x, columns: cols, domain: [x[0], x[x.length - 1]], markers, rules: [{ y: L, label: t("ruleL", { v: L }) }] });
  group.add(new LineChart(container, { title: t("calServed"), unit: "req/s", height: 200, series: servedSeries, xFormat,
    yFormat: (v) => num(v, 0), valueFormat: (v) => num(v, 1) }))
    .setData({ x, columns: cols, domain: [x[0], x[x.length - 1]], markers });
}

/* -------------------------------------------------------------- page chrome */

function applyText() {
  document.documentElement.lang = lang;
  for (const node of document.querySelectorAll("[data-i18n]")) node.textContent = t(node.dataset.i18n);
  document.getElementById("lang-toggle").textContent = t("langButton");
}

function selectTab(name) {
  for (const button of document.querySelectorAll(".tabs button")) button.setAttribute("aria-selected", String(button.dataset.tab === name));
  document.getElementById("tab-live").hidden = name !== "live";
  document.getElementById("tab-experiments").hidden = name !== "experiments";
  if (name === "experiments") loadExperiments();
  if (name === "experiments" || location.hash === "#experiments") location.hash = name === "live" ? "" : name;
}

function setWindow(seconds) {
  live.windowSeconds = seconds;
  writePreference("aegis-window", String(seconds));
  for (const button of document.querySelectorAll("#window-picker button")) {
    button.setAttribute("aria-pressed", String(Number(button.dataset.window) === seconds));
  }
  renderLive();
}

function setTheme(theme) {
  if (theme === "auto") document.documentElement.removeAttribute("data-theme");
  else document.documentElement.setAttribute("data-theme", theme);
  writePreference("aegis-theme", theme);
}

function init() {
  setTheme(readPreference("aegis-theme") || "auto");
  applyText();
  buildLiveCharts();
  for (const button of document.querySelectorAll(".tabs button")) button.addEventListener("click", () => selectTab(button.dataset.tab));
  for (const button of document.querySelectorAll("#window-picker button")) {
    button.addEventListener("click", () => setWindow(Number(button.dataset.window)));
  }
  document.getElementById("theme-toggle").addEventListener("click", () => {
    const order = ["auto", "light", "dark"];
    const current = readPreference("aegis-theme") || document.documentElement.dataset.theme || "auto";
    setTheme(order[(order.indexOf(current) + 1) % order.length]);
  });
  document.getElementById("lang-toggle").addEventListener("click", () => {
    lang = lang === "es" ? "en" : "es";
    writePreference("aegis-lang", lang);
    applyText();
    buildLiveCharts();
    fillReplayPicker();
    renderLive();
    if (experiments.loaded) {
      buildRunPicker();
      buildExperimentCharts();
      renderCalibration();
      renderExperiments();
    }
  });
  document.querySelector(".cycles").addEventListener("toggle", () => renderLive());
  document.getElementById("tech").addEventListener("toggle", () => renderLive());
  document.getElementById("replay-run").addEventListener("change", (event) => switchReplay(event.target.value));
  setWindow(live.windowSeconds);
  selectTab(location.hash === "#experiments" ? "experiments" : "live");
  if (location.hash === "#how") document.getElementById("tech").open = true;
  poll();
  setInterval(poll, POLL_MS);
  setInterval(renderStatus, 1000);
}

init();
