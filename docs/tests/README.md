# Tests

Three tests, one representative run each, on minikube (1 node, 2 CPUs) on 2026-10-19. Calibration used by all of them (`calibration.json`, measured 17:34–17:49 UTC): **C = 24 req/s per pod** (runs: 28, 24), **T = 15 s** (14.2, 13.1). Slow means P95 > L = 1 s for 15 s.

| Test | Traffic | Mode | What it shows |
|---|---|---|---|
| [Test 1](test1-linear-ramp/) | Ramp 5 → 50 req/s in 2 min | Aegis | It asks for the pod before the traffic goes over one pod |
| [Test 2](test2-fluctuating/) | Two waves (30 and 50 req/s) | Aegis | It scales up on each wave and down when the traffic drops |
| [Test 3](test3-hpa-baseline/) | Same ramp as test 1 | HPA only (CPU 70%) | The usual HPA scales late |

## Aegis vs the HPA, same ramp

| | Test 1 (Aegis) | Test 3 (HPA only) |
|---|---|---|
| Traffic passes C | second 81 | second 81 |
| 2nd pod asked | second 71 (10 s before) | second 142 (61 s after) |
| 2nd pod Ready | second 84 | second 154 |
| Failed requests | **0.77%** | **30.65%** |
| Seconds with P95 > 1 s | 40 | 140 |
| Highest pods | 3 | 2 |
| Pod-minutes | 8.6 | 5.6 |

Test 1 was repeated 5 times: the 2nd pod was always asked between second 70 and 75, with 0.24–0.95% failed.

## Test 2 in short
Pods 1 → 2 → 1 → 2 → 3 → 2 → 1, **0.22% failed**. With waves twice as steep, 12.59% failed: Aegis needs about T + 20 ≈ 35 s of visible trend to get ahead.

## Run them again

```bash
cd scripts/experiments
python3 run.py test1-linear-ramp   # or test2-fluctuating, test3-hpa-baseline
python3 report.py                  # charts again from the saved data
```
