# Limitations

Objective OE7; hypotheses H2 (prevention needs a visible trend) and H3 (it can add unneeded pods) of the [methodology](experiments/methodology.md). Data: the 32 runs of 2026-10-25 (C = 22 req/s, T = 15 s, L = 1 s, T_d = 15 s, pod 60m CPU), summarized in [comparison.md](tests/comparison.md). Ranges are min–max.

## 1. How fast the traffic can rise

Between the start of a climb and a Ready pod there are three delays: the demand Aegis sees is ~20 s old (30 s `rate()`), the slope needs the climb inside its 30 s window, and the pod needs T = 15 s. On a linear ramp the pod is requested at `C − m·T + 0.52σ` and Ready at `C + 0.52σ`, whatever the slope, so the limit is how long the climb is visible before reaching C.

| Test | Climb (req/s per s) | Base → C | Runs | Requested ahead of C | Failed |
|---|---:|---:|---:|---|---|
| 1, linear ramp | 0.34 | 50 s | 5 | +6 s (5.5 – 6.5) | 2.5% (0.48 – 4.69) |
| 6, faster ramp | 0.41 | 42 s | 3 | +0.9 s (−2.5 – 2.9) | 1.06% (0.34 – 1.82) |
| 7, faster ramp | 0.46 | 37 s | 3 | −1 s (−1.3 – −0.8) | 1.73% (0.94 – 2.78) |
| Steep waves (first evaluation, C = 24) | 0.58 | 33 s | 1 | −1 s | 12.59% |
| 4, spike | 7.2 | 2.4 s | 5 | −11 s (−11.8 – −11.0) | 13.3% (11.7 – 16.1) |

- **Boundary:** the pod is requested before C when the climb from base to C takes **~40 s or more**. At 0.41–0.46 req/s per s it is requested at the crossing and failures stay at 1–2%; at 0.58 they reach 12.6%.
- Failures do not grow with speed (test 1 failed more than 6 and 7). Most Aegis failures come from the second step (the 46 req/s peak is 5% above 2C) and from C varying between runs (twice in test 1 the single pod degraded at ~17 req/s).
- **Spikes** (5 → 41 req/s in 5 s) give no trend to see. Aegis requests the pod 11 s after the jump and fails 13.3%; the HPA alone requests it 67–112 s after and fails 54.8%. Aegis shortens the degradation (61 vs 104 s) but does not prevent it.

## 2. Cost

| Same load | Aegis | HPA only |
|---|---:|---:|
| **Ramp** (tests 1, 3): failed | 2.5% | 37.1% |
| Seconds degraded | 100 | 162 |
| P95 exposure above L (s × s) | 438 | 1224 |
| Pod-minutes | 8.53 | 5.74 |
| Pod-minutes above the need | +0.95 | −1.84 |
| False alarms | 0 | 0 |
| **Spike** (tests 4, 5): failed | 13.3% | 54.8% |
| Pod-minutes | 7.85 | 4.40 |
| Pod-minutes above the need | +3.10 | −0.35 |
| False alarms per run | 1 | 0.2 |

- On the ramp Aegis spent **+2.8 pod-minutes (+49%)** to cut failures from 37.1% to 2.5%. The HPA saves pods by under-provisioning: it never reached the 3 pods 46 req/s needs.
- The overhead comes from requesting T + lag early and from waiting 60 s of low risk before scaling down. On the waves (test 2) the wait dominates: +4.9 pod-minutes per run.
- **False alarms:** none on ramps and waves. On the spike every run added a 3rd pod the peak did not need (the 30 s slope overshoots right after a jump), ~2.5 pod-minutes each. Damped forecasters overshoot less but request later on ramps ([forecast.md](tests/forecast.md)).

## 3. Metric mode

With the HPA reading the decision through the Custom Metrics API (test 8), each decision reaches the HPA **3–12 s** later (9.5 s on average: scrape, prometheus-adapter, 15 s HPA sync). The first pod is created at ~86 s instead of ~74 s, after the traffic passed C, so it starts under overload and takes ~75 s to be Ready (section 4). Failures rise from 2.5% to **20.2%**. Use `min_replicas` mode unless that path is shortened.

## 4. Assumptions

| Assumption | Breaks when |
|---|---|
| C is stable (fixed CPU limit, one endpoint) | mixed endpoints, noisy neighbours; even here a 60m pod sometimes degraded at ~17 req/s |
| Traefik spreads the load evenly | sticky sessions, long-lived connections |
| All demand passes the Ingress | traffic that bypasses it, keep-alive |
| Projection error is roughly normal | heavy-tailed bursts |
| A pod serves ~T after the request | it starts during an overload (below) |
| Nodes have room | a pod waits for a node (cluster autoscaler adds minutes to T) |

### Pod startup under overload

A pod started before the overload is Ready in 10–11 s. Started during it, it takes **30–90 s**: the 3rd pod in some Aegis runs, the 2nd in the spike tests, every HPA-only and metric-mode run.

Measured with Prometheus and a controlled run (1 pod overloaded, then `minReplicas: 2`):

- The node was mostly idle (8 cores); the new pod used all its 60m quota before being Ready.
- It served 3–14 req/s for ~90 s while its EndpointSlice entry said `ready: false, serving: false`. Traefik v3.7.14 sends traffic to not-ready endpoints; the rule inside Traefik was not identified.
- `/health` shares Node's event loop with the queued requests, so it misses its 5 s timeout until the load drops.

So "Ready" understates the HPA's capacity in the charts; compare request times and k6 failures instead. A fix for production: an ingress that honours readiness, or a health check outside the request queue.

## 5. Threats to validity

- **Repetitions:** 5 runs for the main comparisons, 3 for the rest. Decisions repeat within ±1 s; failure ranges of Aegis and HPA never overlap.
- **Single-node minikube:** k6, Traefik, DynamoDB Local, Prometheus and the pods share one node.
- **Tiny pods:** 60m CPU keeps C at 20–30 req/s on a fast laptop; startup is CPU-bound and overload effects are stronger than with larger pods.
- **Client timeout:** k6 gives up at 10 s, capping P95 at ~10 s.
- **Default HPA baseline** (CPU 70%). A tuned HPA would narrow the gap.
- **Synthetic traffic** chosen by the same person who evaluated it.
- **Max 3 replicas;** behavior at `maxReplicas` was not stressed.
- **Hygiene:** 5 runs of a first pass were invalid (the HPA started with 2 pods, or k6 did not start). They are in `archive/invalid-2026-10-25/` and were repeated after fixing the reset.

## 6. When not to use Aegis

- Traffic made of instant spikes: schedule capacity instead.
- Capacity that varies a lot per request, unless C is calibrated per mix.
- Startups of minutes: the horizon and its error grow.
- Acting only through the Custom Metrics API with default intervals.
