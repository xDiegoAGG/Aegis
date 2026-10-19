# 13 — Reproducible environment (`scripts/setup.sh`)

**Date:** 2026-10-15
**Time:** 04:01:47 – 04:12 UTC (approx.)
**Goal:** check that one command brings the environment back after the machine was off, that running it again changes nothing, and that the books table now survives a minikube restart.

## Setup
- minikube had been stopped for about 5 days. After `minikube start`, `/api/books` returned **500**: DynamoDB Local ran with `-inMemory` and the table was gone (the same problem as on 2026-10-13).
- Changes tested:
  - `scripts/setup.sh`: starts minikube if needed, enables metrics-server, builds the `catalog-service` image if missing, installs Prometheus (`kube-prometheus-stack` 91.7.0, the version already installed), applies DynamoDB Local, seeds the table, applies `catalog-service`, ServiceMonitor and HPA, deletes finished k6 Jobs and runs the check.
  - `scripts/check_env.py`: 5 checks with kubectl only (Prometheus through the API server proxy, no tunnel).
  - Table seed as a Kubernetes Job (`kubernetes/seed-books-job.yaml`) using the `catalog-service` image and `services/catalog-service/seed/seed.js`. It replaces `scripts/db_setup.py`, which needed a port-forward. The 44 test books now have fixed values instead of random ones, so every environment gets the same table.
  - DynamoDB Local stores its data in an `emptyDir` (`-dbPath /data`) instead of memory.
  - Images pinned: `amazon/dynamodb-local:3.3.2` and `grafana/k6:2.3.0` (the versions that were cached as `latest`).
- No traffic, so no chart.

## Results

| Step | Result |
|---|---|
| `check_env.py` before the setup | 1 failure: `/api/books returned 500 (is the table seeded?)`. The other 4 checks passed |
| `setup.sh --build` (first run) | Exit 0 in ~2 min. Image rebuilt, table created and seeded with 50 books, HPA for Aegis applied (CPU 95%), all 5 checks OK |
| `setup.sh` (second run) | Exit 0 in 31 s. Nothing to rebuild or reinstall, all 5 checks OK |
| `minikube stop` + `minikube start`, then `check_env.py` | All 5 checks OK: **50 books still there** without seeding again |

The 5 checks: `catalog-service` answers with 50 books, Prometheus scrapes `catalog-service`, kube-state-metrics reports its replicas (Aegis needs it), the HPA exists, metrics-server has CPU data.

**Conclusion:** after the machine is off, one command (`scripts/setup.sh`) leaves everything ready, and running it again is safe. The table no longer disappears when minikube restarts.

## Not tested yet
- A completely new cluster (`minikube delete` first). The Prometheus install step was skipped because it was already installed.
- The data is still lost if the DynamoDB Local pod is deleted (for example on a new node in EKS). Then `setup.sh` re-seeds it.
