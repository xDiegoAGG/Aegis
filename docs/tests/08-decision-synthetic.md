# 08 — Decision engine with synthetic scenarios (`app/aegis/decision.py`)

**Date:** 2026-09-28
**Goal:** check that the engine turns the risk into the right orders (scale up, scale down, hold) in controlled cases, without touching the cluster.

## Setup
- Made-up traffic, one sample every 5 s, fed through the real risk calculator and then the decision engine, with the values from `config.yaml` (70% up, 30% for 60 s down, 1 to 3 replicas).
- To look like a real cluster, each requested replica becomes Ready 15 s after the engine asks for it.
- No chart, because there was no real traffic.

## Rules tested
- **Scale up:** risk ≥ 70% → one more replica, up to 3.
- **Scale down:** risk < 30% for 60 s in a row → one less replica, down to 1.
- Risk is evaluated with the replicas **already requested**, not only the Ready ones. The projection looks 13 s ahead, which is the time a requested pod needs to be Ready.
- Scale-down checks the risk with **one replica less**. That prevents flapping: with 2 pods and 25 req/s the risk is 0%, but with 1 pod it would be 100%, so it must not scale down.

## Results

| Scenario | Expected | Obtained |
|---|---|---|
| A. Demo ramp 5 → 30 → 5 req/s | One scale-up near 16–17 req/s; scale down ~60 s after traffic drops | Up 1 → 2 at 16.5 req/s (risk 73.1%); down 2 → 1 at t = 290 s, 60 s after traffic went low |
| B. Steady 25 req/s | Up to 2 and stay there | Up 1 → 2, never scales down |
| C. Low dip shorter than 60 s | Timer resets, no scale-down | Stays at 2 |
| D. 60 req/s | 1 → 2 → 3, then hold at the max | 1 → 2 → 3 in two consecutive samples, then holds |
| E1. 10 s data gap while risk is low | Short gap does not break the count | Scales down at t = 60 s as if nothing happened |
| E2. 45 s data gap while risk is low | Timer resets when there is no data | Scales down 60 s after data came back (t = 135 s) |
| F. Low traffic at 1 replica | Never below 1 | Stays at 1 |
| G. Steady 30 req/s | Exactly 2 pods (capacity 36), no 3rd | Up 1 → 2, never asks for a 3rd |

**Conclusion:** the engine scales up once when needed, does not ask for replicas it does not need, and only scales down when one replica less is safe for a full minute.

## Design change found by this test
The first version evaluated the risk with the Ready replicas only, plus a 30 s cooldown after each scale-up. When replayed on real data (test 09), it asked for a 3rd replica 30 s after the 2nd one, because the new pod was not Ready yet and the risk was still 100%. Evaluating the risk with the replicas already requested fixed it (scenario G) and made the cooldown unnecessary, so it was removed from `config.yaml`.
