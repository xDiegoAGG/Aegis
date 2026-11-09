// Readiness that a saturated pod still answers.
//
// /health on the main port waits in the same event loop as the queued requests, so a saturated pod
// missed its 5 s probe 3 times, Kubernetes marked it not Ready, and capacity dropped by one pod
// right when the Deployment was scaling. Here the probe is served by a worker thread with its own
// event loop and port. It is Ready while the main loop keeps ticking, even slowly: slow means
// saturated, not broken. It is not Ready before the HTTP server listens, or when the main loop has
// not ticked for HEALTH_STALL_SECONDS (truly stuck).
import http from "node:http";
import { Worker, isMainThread, workerData } from "node:worker_threads";

const DEFAULT_PORT = 3004;
const DEFAULT_STALL_SECONDS = 30;
const BEAT_MS = 1000;

// Main thread: start the worker and beat once a second. Call ready() once the HTTP server listens.
export function startHealthServer({
  port = Number(process.env.HEALTH_PORT || DEFAULT_PORT),
  stallSeconds = Number(process.env.HEALTH_STALL_SECONDS || DEFAULT_STALL_SECONDS),
} = {}) {
  const beat = new Int32Array(new SharedArrayBuffer(4)); // seconds since the epoch, 0 = not listening yet
  const worker = new Worker(new URL(import.meta.url), { workerData: { beat: beat.buffer, port, stallSeconds } });
  worker.unref();
  let timer = null;
  const tick = () => Atomics.store(beat, 0, Math.floor(Date.now() / 1000));
  return {
    worker,
    ready() {
      tick();
      if (!timer) timer = setInterval(tick, BEAT_MS).unref();
    },
    stop() {
      clearInterval(timer);
      return worker.terminate();
    },
  };
}

// Worker thread: answer /ready from the last beat.
if (!isMainThread && workerData && workerData.beat) {
  const beat = new Int32Array(workerData.beat);
  http
    .createServer((req, res) => {
      const last = Atomics.load(beat, 0);
      const age = Math.floor(Date.now() / 1000) - last;
      const ok = last > 0 && age <= workerData.stallSeconds;
      res.writeHead(ok ? 200 : 503, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ status: ok ? "Ok" : "NotReady", main_loop_age_s: last > 0 ? age : null }));
    })
    .listen(workerData.port);
}
