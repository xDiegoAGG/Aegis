import { ChartGroup, LineChart, niceStep } from "./plot.js";

const POLL_MS = 2000;
// Colors follow the actor, never the order of selection: Aegis blue, HPA alone orange (style.css).
const ACTOR_COLORS = { aegis: "var(--aegis)", hpa: "var(--hpa)", "hpa-tuned": "var(--hpa-tuned)" };
const actorOf = (mode) => (mode === "hpa" || mode === "hpa-tuned" ? mode : "aegis");
const MODE_NAMES = { es: { hpa: "HPA", "hpa-tuned": "HPA afinado", metric: "Aegis (metric)", aegis: "Aegis" },
  en: { hpa: "HPA", "hpa-tuned": "Tuned HPA", metric: "Aegis (metric)", aegis: "Aegis" } };
// Runs of the experiment design are named <load>-<autoscaler>; the October 2026 ones test<N>-<...>.
const isDesign = (test) => !/^test\d+-/.test(test);
// Prefer the design runs when there are any, so a comparison never mixes the two campaigns.
const samePool = (entries) => (entries.some((e) => isDesign(e.test)) ? entries.filter((e) => isDesign(e.test)) : entries);
const REPEAT_DASHES = [null, "7 4", "2 3"];
const MAX_RUNS = 3;

const TEXT = {
  es: {
    tabLive: "En vivo", tabExperiments: "Experimentos", all: "Todo",
    waitingTitle: "Esperando el primer ciclo de Aegis",
    waitingBody: "Este panel lo sirve Aegis. Arráncalo en vivo o reproduce una corrida grabada:",
    versusTitle: "Aegis frente a los HPA, con la misma carga",
    versusLead: "Con esta misma carga ({n} corridas de cada uno), con el HPA solo fallaron de media <b>{hpa}</b> de las peticiones; con Aegis, <b>{aegis}</b>.",
    versusLead3: "Con esta misma carga ({n} corridas de cada uno), fallaron de media: con Aegis <b>{aegis}</b> de las peticiones, con el HPA por defecto <b>{hpa}</b> y con el HPA afinado <b>{tuned}</b>.",
    vsPanelOwn: "{who} · {f} fallidas", vsPanelMedian: "{who} · {f} fallidas",
    replayDesign: "Campaña de bloques aleatorizados: {desc}",
    vsMeanOf: "Media de {n} corridas", vsAskAt: "Pide el 2º pod a los",
    vsNote3: "Los paneles muestran esta corrida de Aegis y la corrida mediana de cada HPA (por peticiones fallidas), con la misma escala. En rojo, el tráfico enviado por el % que falló en cada intervalo de 5 s. La tabla son medias de todas las corridas; en negrita, la mejor.",
    vsAsk: "Pide el 2º pod", vsFailed: "Peticiones fallidas", vsSlow: "Segundos con el servicio lento", vsCost: "Costo (pods-minuto)",
    vsBefore: "{s} s, {d} s antes de superar un pod", vsAfter: "{s} s, {d} s después de superar un pod", vsNever: "nunca",
    vsPanelAegis: "Con Aegis: {f} % fallidas", vsPanelHpa: "Solo HPA: {f} % fallidas",
    vsTraffic: "tráfico enviado", vsCapacity: "capacidad (pods listos × C)", vsLost: "tráfico que falló", vsAskPod: "pide pod {n}",
    vsMissing: "Esta carga no se probó con el HPA solo. Elige la prueba 1 (rampa) o la 4 (pico) para ver la comparación.",
    presetsTitle: "Comparaciones principales", presetLabel: "{profile}: Aegis contra los HPA",
    pickTitle: "O elige hasta 3 corridas", testGroup: "Prueba {n}: {mode}, {profile}", runNumber: "corrida {n}",
    designGroup: "{Profile}: {mode}", blockNumber: "bloque {n}", designName: "{mode}, {profile}, bloque {run}", designShort: "{mode}, bloque {run}",
    mAsk: "Pide el 2º pod", mSlow: "Segundos con el servicio lento", mCost: "Costo (pods-minuto)", mChangeAt: "{from}→{to} a los {s} s",
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
    tankKey: "El agua es el tráfico que recibe cada pod (Traefik lo reparte por igual). La línea punteada es el nivel esperado en {h} s. Un pod punteado no está listo: está arrancando, o está tan saturado que no responde a su chequeo de salud.",
    historyTitle: "Últimos minutos", decisionsTitle: "Qué hizo Aegis",
    lTraffic: "tráfico", lCapacity: "capacidad con Aegis", lForecast: "en {h} s", lProjection: "proyección (zona sombreada: el horizonte)",
    upEvent: "Pidió el pod {n}", downEvent: "Apagó el pod {n}", downEventMany: "Apagó los pods {from} a {to}",
    upWhy: "En {h} s esperaba {p} req/s y {n} {podsWord} {serveVerb} {cap}. Probabilidad de no alcanzar: {risk}.",
    downWhy: "El tráfico bajó: con {n} {podsWord} la probabilidad de no alcanzar se quedó bajo {down} el tiempo de espera ({wait}), así que sobraban.",
    waitRange: "entre {min} y {max} s, menos cuanto más bajo el riesgo", waitFixed: "{max} s",
    noDecisions: "Todavía no cambió nada: Aegis mantiene los pods.",
    markUp: "+1 pod", markDown: "−1 pod",
    techTitle: "Cómo decide Aegis", techHint: "La fórmula y las señales que usa en cada ciclo",
    fDemand: "tráfico que llega", fTrend: "cuánto sube por segundo", fHorizon: "lo que tarda un pod en estar listo (T + retraso)",
    fForecast: "tráfico esperado", fCapacity: "lo que aguantan los pods pedidos", fError: "cuánto se equivoca la proyección",
    fRisk: "probabilidad de no alcanzar", fRule: "Pide un pod si pasa de {up}. Apaga pods si, con menos pods, se queda bajo {down} el tiempo de espera ({wait}).",
    chartForecast: "Qué tan bien predice", chartForecastNote: "Cada proyección dibujada en el momento al que apuntaba, junto al tráfico que de verdad llegó.",
    chartRisk: "Probabilidad de no alcanzar en {h} s", chartRiskNote: "Sobre la línea de {up} Aegis pide un pod. La línea gris es la misma cuenta con un pod menos: si se queda bajo {down} el tiempo de espera, apaga uno.",
    chartPods: "Pods", chartPodsNote: "Los que pidió Aegis, los que ya están listos y lo que hace el HPA.",
    chartLatency: "Lentitud (P95)", chartLatencyNote: "El 95 % de las peticiones tarda menos que esto. Sobre {l} s el servicio se considera lento.",
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
    experimentsTitle: "Explorar las corridas",
    resultsTitle: "Resultados de la campaña",
    resultsLead: "Aegis tuvo menos peticiones fallidas que el HPA en <b>{n} de {total}</b> comparaciones registradas de antemano. 54 corridas: 3 autoscalers × 3 cargas × 6 bloques, en orden aleatorio.",
    resultsH2: "La ventaja no depende solo de anticipar: en el pico, donde no hay tendencia, es tan grande como en la rampa (diferencia {d} puntos, p = {p}).",
    resultsFoot: "Cada punto es una corrida (un bloque); la raya es la media de los 6 bloques. Misma escala en los tres paneles. Análisis completo: docs/tests/design-results.md · plan: docs/experiments/design.md.",
    mFailedPct: "Peticiones fallidas", mDegraded: "Segundos degradado", mPodMin: "Pods-minuto", mAsk2: "Pide el 2º pod",
    noteFailed: "Métrica principal. Lo que nota el usuario, medido por k6. Menos es mejor.",
    noteDegraded: "Secundaria. Segundos con P95 > 1 s o > 1 % de fallos durante 15 s. Menos es mejor.",
    notePodMin: "Secundaria. Costo: pods pedidos × tiempo, en la misma ventana para todos (carga + 6 min). Menos es mejor.",
    noteAsk2: "Secundaria. Segundos desde el inicio de la carga hasta pedir el 2º pod. Antes es mejor.",
    loadRamp: "Rampa", loadSpike: "Pico", loadWaves: "Olas",
    verdictYes: "Aegis menor, significativo", verdictNo: "No se demostró diferencia", verdictWorse: "Aegis mayor",
    basisHolm: " (Holm)", basisRanks: " (Holm, por rangos)", basisExploratory: " (exploratoria)",
    vsDefault: "frente al HPA por defecto", vsTuned: "frente al HPA afinado",
    blockLabel: "Bloque {b}",
    tableView: "Ver como tabla", tLoad: "Carga", tActor: "Autoscaler", tMean: "Media", tRange: "Mín – máx", tRuns: "Corridas",
    octoberTitle: "Campaña preliminar de octubre de 2026 (un factor a la vez, sin aleatorizar)",
    runHint: "Las corridas se dibujan sobre el mismo eje: segundos desde que empezó la carga.",
    noTestsTitle: "No hay corridas grabadas",
    noTestsBody: "Se leen de docs/tests: arranca Aegis o el replay desde el repositorio.",
    calibrationTitle: "Calibración: cuánto aguanta un pod y cuánto tarda en arrancar",
    eTraffic: "Carga enviada (gris punteada) y demanda medida", ePods: "Pods listos (los que atienden)", eAsk: "pide 2º",
    eLegend: "Azul: Aegis. Naranja: HPA por defecto. Verde agua: HPA afinado. Si eliges dos corridas del mismo tipo, la segunda va punteada.",
    eLatency: "P95 que vio el cliente", eFailed: "Peticiones fallidas", eRisk: "Probabilidad de no alcanzar, según Aegis",
    secondsAxis: "s desde el inicio", crossesC: "supera C",
    mFailed: "Peticiones fallidas", mReady: "2º pod listo",
    mMaxPods: "Pods máximos", mScale: "Cambios de pods",
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
    versusTitle: "Aegis against the HPAs, same load",
    versusLead: "With this same load ({n} runs each), the HPA alone let <b>{hpa}</b> of requests fail on average; Aegis, <b>{aegis}</b>.",
    versusLead3: "With this same load ({n} runs each), failed requests on average: <b>{aegis}</b> with Aegis, <b>{hpa}</b> with the default HPA and <b>{tuned}</b> with the tuned HPA.",
    vsPanelOwn: "{who} · {f} failed", vsPanelMedian: "{who} · {f} failed",
    replayDesign: "Randomized block campaign: {desc}",
    vsMeanOf: "Mean of {n} runs", vsAskAt: "Asks for the 2nd pod at",
    vsNote3: "The panels show this Aegis run and the median run of each HPA (by failed requests), on one scale. In red, the traffic sent times the % that failed in each 5 s interval. The table holds means of every run; the best in bold.",
    vsAsk: "Asks for the 2nd pod", vsFailed: "Failed requests", vsSlow: "Seconds with the service slow", vsCost: "Cost (pod-minutes)",
    vsBefore: "{s} s, {d} s before one pod is exceeded", vsAfter: "{s} s, {d} s after one pod is exceeded", vsNever: "never",
    vsPanelAegis: "With Aegis: {f} % failed", vsPanelHpa: "HPA alone: {f} % failed",
    vsTraffic: "traffic sent", vsCapacity: "capacity (Ready pods × C)", vsLost: "traffic that failed", vsAskPod: "asks pod {n}",
    vsMissing: "This load was not run with the HPA alone. Pick test 1 (ramp) or test 4 (spike) to see the comparison.",
    presetsTitle: "Main comparisons", presetLabel: "{profile}: Aegis against the HPAs",
    pickTitle: "Or pick up to 3 runs", testGroup: "Test {n}: {mode}, {profile}", runNumber: "run {n}",
    designGroup: "{Profile}: {mode}", blockNumber: "block {n}", designName: "{mode}, {profile}, block {run}", designShort: "{mode}, block {run}",
    mAsk: "Asks for the 2nd pod", mSlow: "Seconds with the service slow", mCost: "Cost (pod-minutes)", mChangeAt: "{from}→{to} at {s} s",
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
    tankKey: "Water is the traffic each pod receives (Traefik splits it evenly). The dashed line is the level expected in {h} s. A dashed pod is not Ready: it is starting, or so saturated that it misses its health check.",
    historyTitle: "Last minutes", decisionsTitle: "What Aegis did",
    lTraffic: "traffic", lCapacity: "capacity with Aegis", lForecast: "in {h} s", lProjection: "projection (shaded: the horizon)",
    upEvent: "Asked for pod {n}", downEvent: "Turned off pod {n}", downEventMany: "Turned off pods {from} to {to}",
    upWhy: "In {h} s it expected {p} req/s and {n} {podsWord} {serveVerb} {cap}. Chance of falling short: {risk}.",
    downWhy: "Traffic dropped: with {n} {podsWord} the chance of falling short stayed under {down} for the wait ({wait}), so the rest were spare.",
    waitRange: "between {min} and {max} s, shorter the lower the risk", waitFixed: "{max} s",
    noDecisions: "Nothing changed yet: Aegis holds the pods.",
    markUp: "+1 pod", markDown: "−1 pod",
    techTitle: "How Aegis decides", techHint: "The formula and the signals it uses every cycle",
    fDemand: "traffic arriving", fTrend: "how much it rises per second", fHorizon: "time a pod needs to be ready (T + delay)",
    fForecast: "expected traffic", fCapacity: "what the requested pods serve", fError: "how wrong the projection is",
    fRisk: "chance of falling short", fRule: "It asks for a pod above {up}. It turns pods off if, with fewer pods, it stays under {down} for the wait ({wait}).",
    chartForecast: "How well it predicts", chartForecastNote: "Each projection drawn at the moment it was made for, next to the traffic that actually arrived.",
    chartRisk: "Chance of falling short in {h} s", chartRiskNote: "Above the {up} line Aegis asks for a pod. The grey line is the same with one pod less: if it stays under {down} for the wait, one is turned off.",
    chartPods: "Pods", chartPodsNote: "Requested by Aegis, already ready, and what the HPA does.",
    chartLatency: "Slowness (P95)", chartLatencyNote: "95 % of requests take less than this. Above {l} s the service counts as slow.",
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
    experimentsTitle: "Explore the runs",
    resultsTitle: "Campaign results",
    resultsLead: "Aegis had fewer failed requests than the HPA in <b>{n} of {total}</b> comparisons registered in advance. 54 runs: 3 autoscalers × 3 loads × 6 blocks, in random order.",
    resultsH2: "The advantage does not only come from anticipating: on the spike, with no trend, it is as large as on the ramp (difference {d} points, p = {p}).",
    resultsFoot: "Each dot is one run (one block); the bar is the mean of the 6 blocks. Same scale in the three panels. Full analysis: docs/tests/design-results.md · plan: docs/experiments/design.md.",
    mFailedPct: "Failed requests", mDegraded: "Seconds degraded", mPodMin: "Pod-minutes", mAsk2: "Asks for the 2nd pod",
    noteFailed: "Primary metric. What users notice, measured by k6. Lower is better.",
    noteDegraded: "Secondary. Seconds with P95 > 1 s or > 1% failed for 15 s. Lower is better.",
    notePodMin: "Secondary. Cost: requested pods × time, same window for all (load + 6 min). Lower is better.",
    noteAsk2: "Secondary. Seconds from the start of the load to asking for the 2nd pod. Earlier is better.",
    loadRamp: "Ramp", loadSpike: "Spike", loadWaves: "Waves",
    verdictYes: "Aegis lower, significant", verdictNo: "No difference shown", verdictWorse: "Aegis higher",
    basisHolm: " (Holm)", basisRanks: " (Holm, on ranks)", basisExploratory: " (exploratory)",
    vsDefault: "against the default HPA", vsTuned: "against the tuned HPA",
    blockLabel: "Block {b}",
    tableView: "Show as a table", tLoad: "Load", tActor: "Autoscaler", tMean: "Mean", tRange: "Min – max", tRuns: "Runs",
    octoberTitle: "Preliminary October 2026 campaign (one factor at a time, not randomized)",
    runHint: "Runs are drawn on one axis: seconds since the load started.",
    noTestsTitle: "No recorded runs",
    noTestsBody: "They are read from docs/tests: start Aegis or the replay from the repository.",
    calibrationTitle: "Calibration: how much one pod serves and how long it takes to start",
    eTraffic: "Load sent (grey dotted) and measured demand", ePods: "Ready pods (the ones serving)", eAsk: "asks 2nd",
    eLegend: "Blue: Aegis. Orange: default HPA. Aqua: tuned HPA. If you pick two runs of the same kind, the second one is dashed.",
    eLatency: "P95 seen by the client", eFailed: "Failed requests", eRisk: "Chance of falling short, per Aegis",
    secondsAxis: "s since the start", crossesC: "passes C",
    mFailed: "Failed requests",
    mReady: "2nd pod Ready",
    mMaxPods: "Max pods", mScale: "Pod changes",
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

// A share of failed requests: never "0.0" for a value that is not zero (0.03 % stays 0.03 %).
function failedPct(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "–";
  const digits = value === 0 ? 0 : value < 0.1 ? 2 : 1;
  return Number(value).toFixed(digits) + (lang === "es" ? " %" : "%");
}

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
      { key: "rps", label: t("lTraffic"), endLabel: t("lTraffic"), color: "var(--traffic)", fill: true, width: 2, connect: true },
      { key: "capacity", label: t("lCapacity") + " (" + t("sReady") + ")", endLabel: t("lCapacity"), color: "var(--aegis)", step: true, width: 2.5, connect: true },
    ],
    legendExtra: [{ label: t("lProjection"), color: "var(--forecast)", width: 2, dash: "5 4" }],
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
      { key: "rps", label: t("sDemand"), color: "var(--traffic)", width: 2, connect: true },
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
      { key: "target", label: t("sTarget"), color: "var(--aegis)", step: true, width: 3 },
      { key: "ready", label: t("sReady"), color: "var(--ink)", step: true, width: 1.5 },
      { key: "hpaDesired", label: t("sHpa"), color: "var(--quiet)", step: true, dash: "2 3", width: 1.5 },
    ] });
  add("latency", { title: t("chartLatency"), note: t("chartLatencyNote"), unit: "s", height: 130, yMaxAtLeast: 0.5,
    yFormat: (v) => num(v, 1), valueFormat: (v) => num(v, 3) + " s",
    series: [{ key: "p95", label: t("sP95"), color: "var(--ink)" }] });
  add("sigma", { title: t("chartSigma"), note: t("chartSigmaNote"), unit: "req/s", height: 120,
    yFormat: (v) => num(v, 1), valueFormat: (v) => num(v, 2), series: [{ key: "sigma", label: t("sSigma"), color: "var(--forecast)" }] });
  add("slope", { title: t("chartSlope"), note: t("chartSlopeNote"), unit: "req/s²", height: 120, yMin: null, yMaxAtLeast: 0.1,
    yFormat: (v) => num(v, 2), valueFormat: (v) => signed(v, 3), series: [{ key: "slope", label: t("sSlope"), color: "var(--traffic)" }] });
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
    capacity: records.map((r) => (r.replicas_ready === null ? null : C * r.replicas_ready)) };
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
  // Labels of markers less than 40 s apart go on alternate rows so they do not overlap.
  markers.forEach((m, i) => { m.row = i && m.x - markers[i - 1].x < 40 && !markers[i - 1].row ? 1 : 0; });
  live.charts.traffic.setData({
    x, columns: traffic, domain: [domain[0], last.time + horizon + 2], markers, now: last.time,
    zones: [{ x0: last.time, x1: last.time + horizon }],
    segments: [{ x0: last.time, y0: last.rps, x1: last.time + horizon, y1: last.projected_rps === null ? null : Math.max(0, last.projected_rps), color: "var(--forecast)",
      label: last.projected_rps === null ? "" : t("lForecast", { h: num(horizon, 0) }) + ": " + num(Math.max(0, last.projected_rps), 0) }],
  });
  const upPct = meta.scale_up_threshold * 100;
  const downPct = meta.scale_down_threshold * 100;
  // Titles and notes from the running configuration, never from numbers written in the text.
  live.charts.risk.setTitle(t("chartRisk", { h: num(horizon, 0) }));
  live.charts.risk.setNote(t("chartRiskNote", { up: num(upPct, 0) + " %", down: num(downPct, 0) + " %" }));
  live.charts.latency.setNote(t("chartLatencyNote", { l: meta.p95_threshold_seconds }));
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
// The wait before turning pods off: fixed in older runs, 15-60 s by risk since November 2026.
const minWait = (meta) => meta.scale_down_min_wait_seconds ?? meta.scale_down_sustained_seconds;
const waitText = (meta) => (minWait(meta) === meta.scale_down_sustained_seconds ? t("waitFixed", { max: meta.scale_down_sustained_seconds })
  : t("waitRange", { min: minWait(meta), max: meta.scale_down_sustained_seconds }));
const serveVerb = (n) => (n === 1 ? t("serveOne") : t("serveMany"));

// Recorded runs that can be replayed: the ones with an Aegis log (not the HPA-only tests).
const replay = { runs: null, all: null, loading: false, rows: {} };

async function loadReplayRuns() {
  if (replay.runs || replay.loading) return;
  replay.loading = true;
  try {
    const catalog = await (await fetch("api/tests", { cache: "no-store" })).json();
    replay.all = [];
    for (const test of catalog.tests) for (const summary of test.runs) replay.all.push({ test: test.name, summary });
    replay.runs = replay.all.filter((entry) => actorOf(entry.summary.mode) === "aegis");
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
  // Same campaign and same load; the median run of each HPA by failed requests.
  const pool = replay.all.filter((e) => isDesign(e.test) === isDesign(aegis.test) && e.summary.profile === aegis.summary.profile);
  const group = {};
  for (const actor of DESIGN_ACTORS) {
    group[actor] = pool.filter((e) => e.summary.mode === actor).sort((a, b) => a.summary.failed_percent - b.summary.failed_percent);
  }
  const median = (runs) => (runs.length ? runs[Math.floor((runs.length - 1) / 2)] : null);
  const panels = [{ actor: "aegis", entry: aegis, own: true }];
  for (const actor of ["hpa", "hpa-tuned"]) {
    const entry = median(group[actor]);
    if (entry) panels.push({ actor, entry });
  }
  for (const panel of panels) panel.rows = runRows(panel.entry);
  return { aegis, group, panels };
}

// Rows of a recorded run (every 5 s since k6 started), fetched once.
function runRows(entry) {
  const id = entry.test + "/" + entry.summary.run;
  if (replay.rows[id] === undefined) {
    replay.rows[id] = "loading";
    fetch("api/tests/" + id, { cache: "no-store" }).then((r) => r.json())
      .then((run) => { replay.rows[id] = run.rows; renderLive(); })
      .catch(() => { replay.rows[id] = null; });
  }
  return Array.isArray(replay.rows[id]) ? replay.rows[id] : null;
}

// Aegis and the HPA alone side by side: same load, same scales, red where requests failed.
const versus = { key: null };

function renderVersusCharts(pair, C) {
  const box = document.getElementById("versus-charts");
  const ready = pair.panels.every((p) => p.rows);
  const key = [lang, ...pair.panels.map((p) => p.entry.test + p.entry.summary.run), ready].join("|");
  if (versus.key === key) return;
  versus.key = key;
  box.replaceChildren();
  box.classList.toggle("three", pair.panels.length === 3);
  if (!ready) return;
  const value = (v) => (v === null || v === undefined || v === "" ? null : Number(v));
  let top = 0;
  let end = 0;
  for (const panel of pair.panels) {
    panel.color = ACTOR_COLORS[panel.actor];
    panel.title = t(panel.own ? "vsPanelOwn" : "vsPanelMedian", { who: MODE_NAMES[lang][panel.actor],
      f: failedPct(panel.entry.summary.failed_percent) });
    panel.x = panel.rows.map((r) => Number(r.seconds));
    panel.columns = {
      traffic: panel.rows.map((r) => value(r.planned_rps)),
      capacity: panel.rows.map((r) => (value(r.ready) === null ? null : C * value(r.ready))),
      lost: panel.rows.map((r) => (value(r.planned_rps) === null || value(r.client_failed_ratio) === null ? null
        : value(r.planned_rps) * value(r.client_failed_ratio))),
    };
    for (const v of [...panel.columns.traffic, ...panel.columns.capacity]) if (v !== null) top = Math.max(top, v);
    end = Math.max(end, panel.x[panel.x.length - 1] || 0);
  }
  top = Math.ceil((top * 1.05) / 10) * 10;
  const group = new ChartGroup();
  for (const panel of pair.panels) {
    const s = panel.entry.summary;
    const markers = (s.scale_ups || []).map((c, i) => ({ x: c.s, kind: "up", label: t("vsAskPod", { n: c.to }), color: panel.color, row: i % 2 }));
    if (s.crosses_c_s !== null && s.crosses_c_s !== undefined) markers.push({ x: s.crosses_c_s, kind: "info", label: t("crossesC"), row: 2 });
    const chart = group.add(new LineChart(box, {
      title: panel.title, unit: "req/s", height: 230, yMax: top,
      xFormat: (v, long) => Math.round(v) + (long ? " " + t("secondsAxis") : " s"), timeTicks: true,
      yFormat: (v) => num(v, 0), valueFormat: (v) => num(v, 1) + " req/s",
      series: [
        { key: "traffic", label: t("vsTraffic"), color: "var(--traffic)", fill: true, width: 2, connect: true },
        { key: "capacity", label: t("vsCapacity"), color: panel.color, step: true, width: 3, connect: true },
        { key: "lost", label: t("vsLost"), color: "var(--alarm)", fill: true, fillOpacity: 0.45, width: 1.5, connect: true },
      ],
    }));
    chart.setData({ x: panel.x, columns: panel.columns, domain: [0, end], markers });
  }
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
  if (pair.panels.length < 2) {
    lead.textContent = "";
    note.textContent = t("vsMissing");
    document.getElementById("versus-charts").replaceChildren();
    versus.key = null;
    return;
  }
  renderVersusCharts(pair, meta.pod_capacity_rps);
  const actors = DESIGN_ACTORS.filter((a) => pair.group[a].length);
  const mean = (actor, key) => {
    const v = pair.group[actor].map((e) => e.summary[key]).filter((x) => x !== null && x !== undefined);
    return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null;
  };
  const failed = Object.fromEntries(actors.map((a) => [a, failedPct(mean(a, "failed_percent"))]));
  lead.innerHTML = t(actors.includes("hpa-tuned") ? "versusLead3" : "versusLead", { n: pair.group.aegis.length,
    aegis: failed.aegis, hpa: failed.hpa, tuned: failed["hpa-tuned"] });
  const head = el("tr", "", el("thead", "", table));
  el("th", "", head, t("vsMeanOf", { n: pair.group.aegis.length }));
  for (const actor of actors) {
    const th = el("th", actor, head);
    th.appendChild(lineKey(ACTOR_COLORS[actor], null, "swatch"));
    th.appendChild(document.createTextNode(MODE_NAMES[lang][actor]));
  }
  const body = el("tbody", "", table);
  const cost = pair.aegis.summary.pod_minutes_window !== undefined ? "pod_minutes_window" : "pod_minutes";
  const rows = [
    [t("vsFailed"), "failed_percent", failedPct],
    [t("vsSlow"), "degraded_seconds", (v) => num(v, 0) + " s"],
    [t("vsAskAt"), "first_scale_up_s", (v) => num(v, 0) + " s"],
    [t("vsCost"), cost, (v) => num(v, 1)],
  ];
  for (const [label, key, format] of rows) {
    const row = el("tr", "", body);
    el("td", "", row, label);
    const values = actors.map((a) => mean(a, key));
    const best = Math.min(...values.filter((v) => v !== null));
    actors.forEach((actor, i) => el("td", actor + (values[i] === best ? " better" : ""), row, values[i] === null ? "–" : format(values[i])));
  }
  note.textContent = t("vsNote3");
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
  const note = document.getElementById("replay-note");
  // Design runs (<load>-<autoscaler>): describe the load; October runs: their test number.
  const load = (meta.source || "").match(/^(ramp|spike|waves)-/);
  if (load) note.textContent = t("replayDesign", { desc: t({ ramp: "test1", spike: "test4", waves: "test2" }[load[1]]) });
  else note.textContent = t("replayNote", { n, desc: TEXT[lang]["test" + n] ? t("test" + n) : t("testOther") });
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
  term2("C · N", num(C, 0) + " × " + N + " = " + num(C * N, 0), t("fCapacity"), "t-aegis");
  el("span", "op", second, "·");
  term2("σ", num(r.sigma_rps, 1), t("fError"));
  el("span", "op", second, "→");
  term2("Φ((p − C·N) / σ)", pct(r.risk), t("fRisk"), r.risk !== null && r.risk >= meta.scale_up_threshold ? "t-alarm" : "");
  el("p", "formula-rule", box, t("fRule", { up: pct(meta.scale_up_threshold, 0), down: pct(meta.scale_down_threshold, 0), wait: waitText(meta) }));
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
    const many = !up && r.previous_target - r.target > 1;
    el("span", "what", head, up ? t("upEvent", { n: r.target })
      : many ? t("downEventMany", { from: r.target + 1, to: r.previous_target }) : t("downEvent", { n: r.previous_target }));
    el("span", "when", head, clock(r.time));
    const why = up
      ? t("upWhy", { h: num(horizonOf(meta), 0), p: num(r.projected_rps, 0), n: r.previous_target,
        podsWord: podsWord(r.previous_target), serveVerb: serveVerb(r.previous_target), cap: num(C * r.previous_target, 0), risk: pct(r.risk, 0) })
      : t("downWhy", { down: pct(meta.scale_down_threshold, 0), n: r.target, podsWord: podsWord(r.target), wait: waitText(meta) });
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
    [t("pDownWait"), "", minWait(meta) === meta.scale_down_sustained_seconds ? meta.scale_down_sustained_seconds + " s"
      : minWait(meta) + "–" + meta.scale_down_sustained_seconds + " s"],
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
  const mode = MODE_NAMES[lang][entry.summary.mode] || "Aegis";
  const profile = TEXT[lang].profiles[entry.summary.profile] || entry.summary.profile;
  if (isDesign(entry.test)) return t(short ? "designShort" : "designName", { mode, profile, run: entry.summary.run });
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
  document.getElementById("empty-experiments").hidden = experiments.runs.length > 0;
  try {
    experiments.design = (await (await fetch("api/design", { cache: "no-store" })).json()).results;
  } catch {
    experiments.design = null;
  }
  renderResults();
  experiments.presets = buildPresets();
  experiments.selected = experiments.presets.length ? experiments.presets[0].ids.slice() : experiments.runs.slice(0, 2).map((e) => e.id);
  buildRunPicker();
  buildExperimentCharts();
  renderCalibration();
  await renderExperiments();
}

/* ------------------------------------------------- campaign results (design) */

// The responses shown, in the order of the plan: the primary first. All of them: lower is better.
const RESULT_METRICS = [
  { key: "failed_percent", label: "mFailedPct", note: "noteFailed", unit: "%", digits: 1 },
  { key: "degraded_seconds", label: "mDegraded", note: "noteDegraded", unit: " s", digits: 0 },
  { key: "pod_minutes_window", label: "mPodMin", note: "notePodMin", unit: "", digits: 1 },
  { key: "first_scale_up_s", label: "mAsk2", note: "noteAsk2", unit: " s", digits: 0 },
];
const DESIGN_LOADS = [["ramp", "loadRamp"], ["spike", "loadSpike"], ["waves", "loadWaves"]];
const DESIGN_ACTORS = ["aegis", "hpa", "hpa-tuned"];
const results = { metric: readPreference("aegis-result-metric") || "failed_percent" };

// {load: {actor: [{block, value}]}} from the summaries of the design runs.
function designValues(metric) {
  const out = {};
  for (const entry of experiments.runs.filter((e) => isDesign(e.test))) {
    const load = entry.test.split("-")[0];
    const actor = entry.summary.mode;
    const value = entry.summary[metric];
    if (value === null || value === undefined) continue;
    ((out[load] = out[load] || {})[actor] = out[load][actor] || []).push({ block: entry.summary.block ?? entry.summary.run, value });
  }
  return out;
}

function renderResults() {
  const box = document.getElementById("results");
  const values = designValues("failed_percent");
  box.hidden = !Object.keys(values).length;
  if (box.hidden) return;
  const design = experiments.design;
  const primary = design ? design.primary : [];
  const lead = document.getElementById("results-lead");
  lead.innerHTML = primary.length ? t("resultsLead", { n: primary.filter((r) => r.significant).length, total: primary.length }) : "";
  if (design && design.interaction) {
    el("span", "results-h2", lead, " " + t("resultsH2", { d: signed(design.interaction.mean, 1), p: num(design.interaction.p, 2) }));
  }
  const picker = document.getElementById("metric-picker");
  picker.replaceChildren();
  for (const metric of RESULT_METRICS) {
    const button = el("button", "", picker, t(metric.label));
    button.type = "button";
    button.setAttribute("aria-pressed", String(metric.key === results.metric));
    button.addEventListener("click", () => {
      results.metric = metric.key;
      writePreference("aegis-result-metric", metric.key);
      renderResults();
    });
  }
  const metric = RESULT_METRICS.find((m) => m.key === results.metric) || RESULT_METRICS[0];
  document.getElementById("metric-note").textContent = t(metric.note);
  document.getElementById("results-foot").textContent = t("resultsFoot");
  const metricValues = designValues(metric.key);
  drawStrips(metric, metricValues, design);
  const old = document.querySelector("#results .strip-table");
  if (old) old.remove();
  const fmt = metric.key === "failed_percent" ? failedPct : (v) => num(v, metric.digits) + metric.unit;
  document.getElementById("results-foot").before(stripTable(metric, metricValues, fmt));
}

// One strip plot per load, the same y scale in all three: every run a dot, the mean a bar, the verdicts below.
function drawStrips(metric, values, design) {
  const box = document.getElementById("strips");
  box.replaceChildren();
  const all = [];
  for (const load of Object.values(values)) for (const runs of Object.values(load)) for (const r of runs) all.push(r.value);
  // Round ticks: a nice step for ~4 intervals, the top a whole number of steps above the highest run.
  const step = niceStep(Math.max(1, ...all) * 1.05, 4);
  const top = Math.ceil((Math.max(1, ...all) * 1.05) / step) * step;
  const fmt = metric.key === "failed_percent" ? failedPct : (v) => num(v, metric.digits) + metric.unit;
  const tooltip = el("div", "chart-tooltip strip-tooltip", box);
  tooltip.hidden = true;
  for (const [load, labelKey] of DESIGN_LOADS) {
    const panel = el("figure", "strip", box);
    el("figcaption", "strip-title", panel, t(labelKey));
    const width = 300;
    const height = 230;
    const m = { top: 12, right: 40, bottom: 30, left: 44 };
    const svgNode = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svgNode.setAttribute("viewBox", "0 0 " + width + " " + height);
    svgNode.setAttribute("class", "strip-svg");
    svgNode.setAttribute("role", "img");
    panel.appendChild(svgNode);
    const add = (tag, attrs, parent = svgNode) => {
      const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
      for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
      parent.appendChild(node);
      return node;
    };
    const sy = (v) => height - m.bottom - (v / top) * (height - m.top - m.bottom);
    const column = (width - m.left - m.right) / DESIGN_ACTORS.length;
    for (let tick = 0; tick <= top + 1e-9; tick += step) {
      add("line", { x1: m.left, x2: width - m.right, y1: sy(tick), y2: sy(tick), class: "strip-grid" });
      add("text", { x: m.left - 6, y: sy(tick), class: "tick tick-y" }).textContent = num(tick, step < 1 ? 1 : 0);
    }
    const described = [];
    DESIGN_ACTORS.forEach((actor, i) => {
      const runs = (values[load] || {})[actor] || [];
      const cx = m.left + column * (i + 0.5);
      add("text", { x: cx, y: height - 10, class: "tick tick-x strip-actor" }).textContent = MODE_NAMES[lang][actor];
      if (!runs.length) return;
      const mean = runs.reduce((a, r) => a + r.value, 0) / runs.length;
      described.push(MODE_NAMES[lang][actor] + " " + fmt(mean));
      const bar = add("line", { x1: cx - 20, x2: cx + 20, y1: sy(mean), y2: sy(mean), class: "strip-mean" });
      bar.style.stroke = ACTOR_COLORS[actor];
      add("text", { x: cx + 24, y: sy(mean), class: "strip-mean-label" }).textContent = fmt(mean);
      for (const r of runs) {
        // A transparent 24 px hit area in front of each 9 px dot: nobody has to land on the dot itself.
        const x = cx + (r.block - 3.5) * 5;
        const hit = add("circle", { cx: x, cy: sy(r.value), r: 12, class: "strip-hit", tabindex: 0,
          "aria-label": MODE_NAMES[lang][actor] + ", " + t("blockLabel", { b: r.block }) + ": " + fmt(r.value) });
        const dot = add("circle", { cx: x, cy: sy(r.value), r: 4.5, class: "strip-dot" });
        dot.style.fill = ACTOR_COLORS[actor];
        const show = () => {
          tooltip.replaceChildren();
          // Value first, then what it is.
          el("strong", "tooltip-value", tooltip, fmt(r.value));
          el("div", "tooltip-x", tooltip, MODE_NAMES[lang][actor] + " · " + t(labelKey) + " · " + t("blockLabel", { b: r.block }));
          tooltip.hidden = false;
          dot.classList.add("active");
          const rect = dot.getBoundingClientRect();
          const host = box.getBoundingClientRect();
          tooltip.style.left = Math.min(host.width - 170, rect.left - host.left + 12) + "px";
          tooltip.style.top = rect.top - host.top - 8 + "px";
        };
        const hide = () => { tooltip.hidden = true; dot.classList.remove("active"); };
        hit.addEventListener("pointerenter", show);
        hit.addEventListener("focus", show);
        hit.addEventListener("pointerleave", hide);
        hit.addEventListener("blur", hide);
      }
    });
    svgNode.setAttribute("aria-label", t(labelKey) + ", " + t(metric.label) + ": " + described.join(", "));
    const verdicts = el("ul", "verdicts", panel);
    for (const [second, vsKey] of [["hpa", "vsDefault"], ["hpa-tuned", "vsTuned"]]) {
      const row = verdictFor(design, metric.key, load, second);
      if (!row) continue;
      const better = row.diff < 0;
      const primary = metric.key === "failed_percent";
      const significant = primary ? row.significant : row.p < 0.05;
      const kind = significant ? (better ? "yes" : "worse") : "no";
      const li = el("li", "verdict " + kind, verdicts);
      el("span", "verdict-icon", li, kind === "yes" ? "✓" : kind === "worse" ? "▲" : "–");
      const basis = !primary ? t("basisExploratory") : row.decided_on === "ranks" ? t("basisRanks") : t("basisHolm");
      el("span", "", li, t(vsKey) + ": " + signed(row.diff, metric.digits) + " [" + signed(row.ci[0], metric.digits) + ", "
        + signed(row.ci[1], metric.digits) + "] · p " + pValue(primary ? row.p_decision : row.p) + basis);
      li.title = t(kind === "yes" ? "verdictYes" : kind === "worse" ? "verdictWorse" : "verdictNo");
    }
  }
}

// The accessible twin of the strip plots: every mean, range and run count in a table.
function stripTable(metric, values, fmt) {
  const details = el("details", "strip-table");
  el("summary", "", details, t("tableView"));
  const table = el("table", "", details);
  const head = el("tr", "", el("thead", "", table));
  for (const label of [t("tLoad"), t("tActor"), t("tMean"), t("tRange"), t("tRuns")]) el("th", "", head, label);
  const body = el("tbody", "", table);
  for (const [load, labelKey] of DESIGN_LOADS) {
    for (const actor of DESIGN_ACTORS) {
      const runs = (values[load] || {})[actor] || [];
      if (!runs.length) continue;
      const v = runs.map((r) => r.value);
      const row = el("tr", "", body);
      el("td", "", row, t(labelKey));
      el("td", "", row, MODE_NAMES[lang][actor]);
      el("td", "", row, fmt(v.reduce((a, b) => a + b, 0) / v.length));
      el("td", "", row, fmt(Math.min(...v)) + " – " + fmt(Math.max(...v)));
      el("td", "", row, String(v.length));
    }
  }
  return details;
}

function verdictFor(design, metric, load, second) {
  if (!design) return null;
  const list = metric === "failed_percent" ? design.primary : design.secondary;
  return list.find((r) => r.load === load && r.second === second && (metric === "failed_percent" || r.metric === metric)) || null;
}

const pValue = (p) => (p < 0.001 ? "< 0.001" : num(p, 3));

// For every load run both with Aegis and with the HPA alone: the median run of each (by failed requests).
function buildPresets() {
  const median = (runs) => runs.slice().sort((a, b) => a.summary.failed_percent - b.summary.failed_percent)[Math.floor((runs.length - 1) / 2)];
  const presets = [];
  for (const profile of [...new Set(samePool(experiments.runs).map((e) => e.summary.profile))]) {
    const pool = samePool(experiments.runs.filter((e) => e.summary.profile === profile));
    const of = (mode) => pool.filter((e) => e.summary.mode === mode);
    if (of("aegis").length && of("hpa").length) {
      presets.push({ profile, ids: ["aegis", "hpa", "hpa-tuned"].filter((m) => of(m).length).map((m) => median(of(m)).id) });
    }
  }
  return presets;
}

function selectRuns(ids) {
  experiments.selected = ids.slice(0, MAX_RUNS);
  for (const box of document.querySelectorAll("#run-picker input")) box.checked = experiments.selected.includes(box.dataset.id);
  renderExperiments();
}

function buildRunPicker() {
  const picker = document.getElementById("run-picker");
  picker.replaceChildren();
  if (experiments.presets.length) {
    el("h2", "", picker, t("presetsTitle"));
    const row = el("div", "presets", picker);
    for (const preset of experiments.presets) {
      const name = TEXT[lang].profiles[preset.profile] || preset.profile;
      const button = el("button", "preset", row, t("presetLabel", { profile: name.charAt(0).toUpperCase() + name.slice(1) }));
      button.type = "button";
      button.addEventListener("click", () => selectRuns(preset.ids));
    }
  }
  el("h2", "", picker, t("pickTitle"));
  const tests = [...new Set(experiments.runs.map((e) => e.test))].sort((a, b) => isDesign(b) - isDesign(a));
  const hasDesign = tests.some(isDesign);
  let october = null;
  for (const test of tests) {
    const runs = experiments.runs.filter((e) => e.test === test);
    let parent = picker;
    if (hasDesign && !isDesign(test)) {
      if (!october) {
        october = el("details", "october", picker);
        el("summary", "", october, t("octoberTitle"));
      }
      parent = october;
    }
    const group = el("fieldset", "run-group", parent);
    const first = runs[0];
    const match = test.match(/^test(\d+)-/);
    const mode = MODE_NAMES[lang][first.summary.mode] || "Aegis";
    const profileName = TEXT[lang].profiles[first.summary.profile] || first.summary.profile;
    el("legend", "", group, isDesign(test)
      ? t("designGroup", { Profile: profileName.charAt(0).toUpperCase() + profileName.slice(1), mode })
      : t("testGroup", { n: match ? match[1] : test, mode, profile: profileName }));
    for (const entry of runs) {
      const label = el("label", "run-box", group);
      label.title = t(isDesign(entry.test) ? "blockNumber" : "runNumber", { n: entry.summary.run });
      const input = el("input", "", label);
      input.type = "checkbox";
      input.dataset.id = entry.id;
      input.checked = experiments.selected.includes(entry.id);
      input.setAttribute("aria-label", runLabel(entry));
      input.addEventListener("change", () => {
        if (input.checked) {
          experiments.selected.push(entry.id);
          if (experiments.selected.length > MAX_RUNS) experiments.selected.shift();
        } else {
          experiments.selected = experiments.selected.filter((id) => id !== entry.id);
        }
        selectRuns(experiments.selected);
      });
      el("span", "", label, String(entry.summary.run));
    }
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
  const entries = experiments.selected.map((id) => experiments.runs.find((e) => e.id === id)).filter(Boolean);
  const seen = {};
  for (const entry of entries) {
    const actor = actorOf(entry.summary.mode);
    seen[actor] = (seen[actor] || 0) + 1;
    entry.color = ACTOR_COLORS[actor];
    entry.dash = REPEAT_DASHES[seen[actor] - 1] || null;
  }
  for (const box of document.querySelectorAll("#run-picker input")) {
    const entry = entries.find((e) => e.id === box.dataset.id);
    box.parentElement.style.setProperty("--run-color", entry ? entry.color : "transparent");
    box.parentElement.classList.toggle("dashed", Boolean(entry && entry.dash));
  }
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
    const look = { color: entry.color, dash: entry.dash };
    seriesFor.traffic.push(Object.assign({ key: id + "demand", label: name }, look),
      { key: id + "planned", label: name + " (plan)", color: "var(--traffic)", dash: "2 3", width: 1.5, hideInLegend: true });
    seriesFor.pods.push(Object.assign({ key: id + "ready", label: name, step: true, width: 2.5 }, look));
    seriesFor.latency.push(Object.assign({ key: id + "p95", label: name }, look));
    seriesFor.failed.push(Object.assign({ key: id + "failed", label: name }, look));
    if (actorOf(entry.summary.mode) === "aegis") seriesFor.risk.push(Object.assign({ key: id + "risk", label: name }, look));
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
  const asks = entries.filter((e) => e.summary.first_scale_up_s !== null && e.summary.first_scale_up_s !== undefined)
    .map((e, i) => ({ x: e.summary.first_scale_up_s, kind: "up", label: t("eAsk"), color: e.color, row: i + 1 }));
  experiments.charts.pods.setData({ x, columns: cols, domain, markers: markers.concat(asks) });
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
    th.appendChild(lineKey(entry.color, entry.dash, "swatch"));
    th.appendChild(document.createTextNode(runLabel(entry)));
  }
  const seconds = (v) => (v === null || v === undefined ? "–" : num(v, 0) + " s");
  const rows = [
    [t("mFailed"), "failed_percent", failedPct, "lower"],
    [t("mSlow"), "degraded_seconds", seconds, "lower"],
    [t("mReady"), "second_pod_ready_s", seconds, "lower"],
    [t("mMaxPods"), "max_pods", (v) => String(v), null],
    // Pod-minutes in the common window (load + tail) when the run has it: the truncated count leaves out the tail.
    [t("mCost"), "pod_minutes_window", (v) => num(v, 1), "lower"],
  ];
  const body = el("tbody", "", table);
  const askRow = el("tr", "", body);
  el("td", "", askRow, t("mAsk"));
  const asks = entries.map((e) => e.summary.first_scale_up_s);
  const firstAsk = Math.min(...asks.filter((v) => v !== null && v !== undefined));
  for (const entry of entries) {
    const s = entry.summary;
    let text = t("vsNever");
    if (s.first_scale_up_s !== null && s.first_scale_up_s !== undefined) {
      const delta = s.crosses_c_s - s.first_scale_up_s;
      text = t(delta >= 0 ? "vsBefore" : "vsAfter", { s: num(s.first_scale_up_s, 0), d: num(Math.abs(delta), 0) });
    }
    el("td", entries.length > 1 && s.first_scale_up_s === firstAsk ? "best" : "", askRow, text);
  }
  for (const [label, key, format, better] of rows) {
    const row = el("tr", "", body);
    el("td", "", row, label);
    const values = entries.map((e) => e.summary[key] ?? (key === "pod_minutes_window" ? e.summary.pod_minutes : null));
    const valid = values.filter((v) => v !== null && v !== undefined);
    let best = null;
    if (better && entries.length > 1 && valid.length > 1) best = better === "lower" ? Math.min(...valid) : Math.max(...valid);
    for (const value of values) el("td", value !== null && value === best ? "best" : "", row, value === null || value === undefined ? "–" : format(value));
  }
  const row = el("tr", "", body);
  el("td", "", row, t("mScale"));
  for (const entry of entries) {
    const changes = entry.summary.scale_ups.concat(entry.summary.scale_downs).sort((a, b) => a.s - b.s)
      .map((c) => t("mChangeAt", { from: c.from, to: c.to, s: Math.round(c.s) }));
    el("td", "", row).appendChild(el("small", "", null, changes.join(", ") || "–"));
  }
}

// A short line in a series color and dash, as in the chart legends.
function lineKey(color, dash, className) {
  const ns = "http://www.w3.org/2000/svg";
  const key = document.createElementNS(ns, "svg");
  key.setAttribute("width", "28");
  key.setAttribute("height", "8");
  key.setAttribute("class", className);
  const line = document.createElementNS(ns, "line");
  for (const [k, v] of Object.entries({ x1: 1, x2: 27, y1: 4, y2: 4 })) line.setAttribute(k, v);
  line.style.stroke = color;
  line.style.strokeWidth = 3;
  if (dash) line.style.strokeDasharray = dash;
  key.appendChild(line);
  return key;
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
  const servedSeries = [{ key: "sent", label: t("calSent"), color: "var(--traffic)", dash: "1 4", width: 1.5 }];
  runs.forEach((run, i) => {
    const byX = new Map(run.steps.map((s) => [s.target_rps, s]));
    cols["p95" + i] = x.map((v) => (byX.has(v) ? byX.get(v).p95_max_s : null));
    cols["served" + i] = x.map((v) => (byX.has(v) ? byX.get(v).measured_rps : null));
    // Calibration runs are neither Aegis nor the HPA: neutral inks, dashed after the first.
    const look = { color: i === 0 ? "var(--ink)" : "var(--quiet)", dash: i === 0 ? null : "5 3", dots: true };
    p95Series.push(Object.assign({ key: "p95" + i, label: t("calRun", { n: i + 1 }) + " (C = " + run.capacity_rps + ")" }, look));
    servedSeries.push(Object.assign({ key: "served" + i, label: t("calRun", { n: i + 1 }) }, look));
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
      renderResults();
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
