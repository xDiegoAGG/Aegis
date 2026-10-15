# 10 — Actuator, manual test (`app/aegis/actuator.py`)

**Date:** 2026-10-13
**Time:** 23:12:52 – 23:19:07 UTC
**Goal:** check that the actuator can change `minReplicas` of the HPA, that Kubernetes follows the change, and that the full loop runs without changing anything in dry-run mode.

## Setup
- minikube restarted after 15 days off. `tb_books` reseeded (50 books), Prometheus tunnel open.
- Actuator running from the local machine with the kubeconfig credentials (`kubernetes` Python client 35.0.0).
- HPA from test 04 still active (CPU 70%, 1 to 3 replicas). No traffic.
- At the start the HPA had 2 replicas: right after the restart the pods used CPU while starting, and the HPA scaled up by itself at ~23:07 UTC.
- No chart, because there was no traffic.

## How the actuator works
- It only changes `spec.minReplicas` of the HPA with a PATCH. It never touches the Deployment: the HPA creates or removes the pods.
- It only calls the API when the target changes. If the call fails it logs a warning and tries again in the next cycle.
- At start it reads the current `minReplicas` and uses it as the starting target, so restarting Aegis does not undo a scale-up.
- Modes: full loop, `--dry-run` (full loop, no changes) and `--set N` (sets `minReplicas` once and exits).

## Results

| Time (UTC) | Action | What happened |
|---|---|---|
| 23:12:52 – 23:13:04 | `--dry-run`, 3 cycles | rps = 0, risk 0%, HOLD at 1. The HPA was not changed |
| 23:13:20 | `--set 3` | `minReplicas` 1 → 3. A 3rd pod was created at once |
| 23:13:47 | — | 3 pods Ready (the new one took less than 26 s) |
| 23:13:52 | `--set 1` | `minReplicas` 3 → 1. Replicas went 3 → 2 within seconds |
| 23:19:03 | — | Replicas 2 → 1, **about 5 minutes later** |
| 23:13:57 | `--set 5` | Rejected by Aegis: outside the 1–3 range in `config.yaml` |

**Conclusion:** the actuator works in both directions. Raising `minReplicas` creates pods right away, which is what Aegis needs to scale up early.

## Finding: the HPA delays every scale-down by 5 minutes
After `minReplicas` goes down, the HPA keeps the extra pods for its default scale-down stabilization window (300 s). It only went 3 → 2 at once because 2 was already its own recommendation from the restart. Aegis already waits 60 s of low risk before scaling down, so this window stacks on top of it. The fix belongs with the next step (raising the HPA CPU threshold): set `behavior.scaleDown.stabilizationWindowSeconds` to 0 (done in `kubernetes/catalog-service-hpa-aegis.yaml`, see below).

## Re-check after the fix
**Time:** 00:18:34 – 00:22:04 UTC (2026-10-14)

Applied `kubernetes/catalog-service-hpa-aegis.yaml`: same HPA, but CPU target at 95% and `behavior.scaleDown.stabilizationWindowSeconds: 0`. The baseline file `catalog-service-hpa.yaml` (CPU 70%) is kept as it is, to repeat test 04 later.

| Time (UTC) | Action | What happened |
|---|---|---|
| 00:18:42 | `--set 2` | 2nd pod Ready at 00:18:56 (14 s, same as $T$) |
| 00:19:03 | `--set 1` right away | Replicas 2 → 1 at 00:19:59, **56 s later** |
| 00:20:25 | `--set 2` | 2nd pod created |
| 00:22:03 | `--set 1` after 90 s | Replicas 2 → 1 at 00:22:04, **in about 1 s** |

The 56 s delay in the first try is not the stabilization window. The new pod did not have CPU metrics yet (metrics-server measures about once per minute), and when a pod has no metrics the HPA assumes it is busy and does not scale down. Once the pod had metrics, scale-down was immediate. In a real run the extra pod will have been running for minutes, so scale-down will follow Aegis right away.

**Conclusion:** with the Aegis HPA, scaling down now takes about 1 s instead of 5 minutes.
