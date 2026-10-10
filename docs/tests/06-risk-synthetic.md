# 06 — Risk calculator with synthetic scenarios (`app/aegis/risk.py`)

**Date:** 2026-09-28
**Goal:** check that the formula gives the expected result in controlled cases, without depending on the cluster.

## Setup
The calculator was fed made-up samples, one every 5 s, with the values from `config.yaml` (C = 18, T = 13, σ = 2, 30 s window). There is no chart because there was no real traffic.

## Results

| Scenario | Expected | Obtained |
|---|---|---|
| Flat traffic at 10 req/s, 1 pod | Risk ~0% | 0.0% on every sample |
| Climbs 1 req/s every 5 s from 8, 1 pod | Crosses 70% **before** reaching 18 req/s | 61.8% at 16 req/s and **78.8% at 17 req/s** |
| 25 req/s with 1 pod | ~100% | 100.0% |
| 25 req/s with 2 pods (capacity 36) | ~0% | 0.0% |

## Edge cases

| Case | Behavior | Result |
|---|---|---|
| A single sample (no slope) | Uses m = 0 | 17 req/s → 30.9% |
| Sample without data (Prometheus failed) | Ignores it, does not count it as 0 | Risk stays at 34.5% instead of dropping |
| 0 Ready replicas (saturated pod) | Counts as 1 replica | 20 req/s → 84.1% (not 100% from dividing by 0) |
| Never had traffic | No risk returned | "No traffic data yet" |

**Conclusion:** the formula and the edge cases behave as designed.
