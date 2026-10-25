# Test 8: Aegis through the Custom Metrics API

**Date:** 2026-10-25, 05:56 – 06:15 UTC, 3 runs
**Goal:** the HPA reads `aegis_target_replicas` through prometheus-adapter; how much later does it act?

## What was done
- Same traffic as [test 1](../test1-linear-ramp/).
- Aegis running **in the cluster** (`kubernetes/aegis/`, `AEGIS_ACTUATOR_MODE=metric`); HPA of `kubernetes/hpa/aegis-metric.yaml` (Object metric `aegis_target_replicas`, target 1, plus CPU 95%).

## Results

![Test 8: Aegis through the Custom Metrics API, all runs](all-runs.png)

| Run | Scale changes (s since k6 started) | 2nd pod Ready (s) | Failed | Seconds degraded | Pod-minutes |
|---|---|---|---|---|---|
| 1 | 1→2 at 87, 2→3 at 147, 3→2 at 297 | 162 | 21.34% | 165 | 8.1 |
| 2 | 1→2 at 86, 2→3 at 146, 3→2 at 311 | 165 | 18.36% | 165 | 8.13 |
| 3 | 1→2 at 84, 2→3 at 144, 3→2 at 309 | 161 | 20.86% | 150 | 8.2 |

Aegis decides as in test 1 (2nd pod at 72–78 s, 3rd at 132–143 s); the HPA created each pod **3–12 s** later (9.5 s on average). That moves the 2nd pod to ~86 s, after the traffic passed C, so it starts under overload and is Ready 68–79 s after creation ([limitations.md](../../limitations.md#pod-startup-under-overload)).

## Conclusion
The path works, but ~10 s is enough to lose the lead: **20.2% failed** against 2.5% in `min_replicas` mode. Use metric mode only if patching HPAs is not allowed, and shorten the path first.

Data: `data/` (files per run) and `results.csv`.
