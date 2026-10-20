# Test 2: Aegis with fluctuating traffic

**Date:** 2026-10-19, 18:58:22 – 19:09:10 UTC
**Goal:** show that Aegis scales up on each wave and **gives the pods back** when the traffic drops.

## What was done
- Traffic (`kubernetes/load/fluctuating.yaml`, 560 s): 30 s at 5 req/s, a wave to 30 req/s (65 s up, 45 s flat), 105 s at 5, a wave to 50 req/s (120 s up, 45 s flat), 120 s at 5. Both waves climb as fast as the ramp of test 1.
- Aegis running with the HPA of `kubernetes/hpa/aegis.yaml`.
- Calibration: C = 24 req/s per pod, T = 15 s. The traffic passes C at second 79 (wave 1) and 311 (wave 2), and 2C (48) at second 375.

## Results

![Test 2](chart.png)

| Second (since k6 started) | What happened |
|---|---|
| 73 | Aegis asks for the 2nd pod (demand 16.1, projection 28.2, risk 78.9%) |
| 79 | The traffic passes C |
| 86 | The 2nd pod is Ready |
| 140–155 | The traffic drops to 5 req/s |
| 223 | **Scale down 2 → 1**: 60 s with risk below 30% with one pod less |
| 303 | Second wave: Aegis asks for the 2nd pod (risk 72.4%), before the traffic passes C at 311 |
| 363 | Aegis asks for the 3rd pod (projection 51.8 > 2C), before the traffic passes 2C at 375 |
| 425–440 | The traffic drops to 5 req/s |
| 498 | **Scale down 3 → 2** |
| 568 | **Scale down 2 → 1** |

k6: 9817 requests, **0.22% failed**, P95 1.89 s. 100 s with P95 above 1 s, in short peaks while a new pod was starting (the node has only 2 CPUs). Pods: 1 → 2 → 1 → 2 → 3 → 2 → 1, 18.4 pod-minutes.

## Conclusion
On both waves Aegis asked for the pod before the traffic passed what the running pods can serve, and after each wave it went back to 1 pod, one step at a time, without going up and down in between.

## Limit: steeper waves
A first version of this test had waves about twice as steep (to 40 req/s in 60 s and to 55 req/s in 45 s). There Aegis asked for the pod at the same moment the traffic passed C, not before, and **12.59% of the requests failed** (`data/steep-waves-summary.json`, `data/steep-waves-chart.png`). Between asking for a pod and having it Ready, Aegis needs about T + 20 ≈ 35 s of visible trend. A faster climb cannot be anticipated with that budget. This is hypothesis H2 of `docs/experiments/methodology.md` and will be measured against the HPA in the formal evaluation.

Data: `data/run-1.csv` (every 5 s), `data/run-1-aegis.ndjson` (every Aegis cycle), `data/run-1-k6.log`, `data/run-1-summary.json`.
