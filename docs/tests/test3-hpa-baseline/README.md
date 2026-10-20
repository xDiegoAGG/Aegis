# Test 3: the plain HPA, without Aegis

**Date:** 2026-10-19, 18:28:04 – 18:32:45 UTC
**Goal:** show that the usual HPA scales late, with the same ramp as [test 1](../test1-linear-ramp/).

## What was done
- Same traffic as test 1 (`kubernetes/load/linear.yaml`): from 5 to 50 req/s in 2 min, 1 min at 50.
- Aegis off. HPA of `kubernetes/hpa/baseline.yaml`: scale on CPU at 70%, Kubernetes defaults.
- One pod serves C = 24 req/s: the traffic passes it at second 81.

## Results

![Test 3](chart.png)

| Second (since k6 started) | What happened |
|---|---|
| 81 | The traffic passes what one pod can serve |
| 96 | The client sees the service degraded (P95 above 1 s) |
| 142 | The HPA asks for the 2nd pod: **61 s after** the traffic passed C, 46 s after the service broke |
| 154 | The 2nd pod is Ready |
| 145–210 | 50 req/s with 2 pods (2C = 48): still overloaded, the HPA never asks for a 3rd pod |

k6: 7006 requests, **30.65% failed**, P95 10 s (the client timeout), 140 s degraded.

## Conclusion
The HPA only reacts when the CPU is already high, and the new pod still needs T seconds. By then the service is broken. Aegis, on the same ramp, asked for the pod 10 s **before** the traffic passed C and failed 0.77% of the requests.

| | Test 1 (Aegis) | Test 3 (HPA only) |
|---|---|---|
| 2nd pod asked | second 71 (10 s before C) | second 142 (61 s after C) |
| 2nd pod Ready | second 84 | second 154 |
| Failed requests | 0.77% | 30.65% |
| Seconds degraded | 40 | 140 |
| Highest pods | 3 | 2 |

Data: `data/run-1.csv`, `data/run-1-k6.log`, `data/run-1-summary.json`.
