# Aegis

Preventive horizontal scaling for Kubernetes services.

The HPA reacts once the CPU is high, and a new pod still needs seconds to be Ready. Aegis projects the traffic, computes the probability of exceeding the pods' capacity, and raises the HPA's `minReplicas` **before** that happens; it lowers it when traffic drops. Every 5 s:

```
Prometheus ──► demand r ──► projection p = r + m·(T + lag) ──► risk = Φ((p − C·N) / σ) ──► 70% up / 30% for 15–60 s down ──► HPA minReplicas
```

- **C** (req/s per pod) and **T** (time until a requested pod is Ready) are measured by calibration; **σ** is learned from the projection errors.
- Formulas: [docs/formulas.md](docs/formulas.md) ([español](docs/formulas.es.md)). Dashboard at http://localhost:8080 ([docs/dashboard.md](docs/dashboard.md)).

## Repository

| Path | What it is |
|---|---|
| `app/aegis/collector.py` | Reads demand, latency and Ready pods from Prometheus |
| `app/aegis/risk.py` | Projection, live σ and risk |
| `app/aegis/decision.py` | Scale-up and scale-down rules |
| `app/aegis/actuator.py` | Main loop: applies the decisions to the HPA `minReplicas` (or only publishes them, `metric` mode) |
| `app/aegis/server.py`, `app/aegis/dashboard/` | Dashboard, `/metrics` for Prometheus and the JSON API |
| `app/aegis/replay.py` | Plays a recorded run on the dashboard, without a cluster |
| `app/aegis/calibrate.py`, `calibration.py` | Measure C and T; save and read them in the cluster |
| `app/config.yaml` | Thresholds, queries, calibration, actuator mode and dashboard port |
| `app/tests/` | Unit tests of projection, σ, risk, decisions and server, and two recorded runs fed again to the engine |
| `app/Dockerfile`, `kubernetes/aegis/` | Aegis inside the cluster: image, least-privilege RBAC, Deployment, ServiceMonitor |
| `kubernetes/monitoring/` | Prometheus recording rules (`aegis:catalog_p95_latency`, `aegis:catalog_rps`, `aegis:replica_count`, ...) and alerts |
| `services/catalog-service/`, `shared/proto/` | The service Aegis protects (from MyBookstore): HTTP and gRPC over DynamoDB |
| `kubernetes/catalog-service/`, `dynamodb/` | The service, its Ingress and ServiceMonitor; DynamoDB Local and the table seed |
| `kubernetes/hpa/` | `aegis.yaml` (Aegis writes `minReplicas`), `aegis-metric.yaml` (the HPA reads the Aegis metric) and `baseline.yaml` (plain HPA, CPU 70%) |
| `kubernetes/load/` | k6 traffic profiles |
| `kubernetes/helm/` | Values for Prometheus, prometheus-adapter and Traefik |
| `scripts/setup.sh`, `scripts/check_env.py` | Bring up and check the whole environment |
| `scripts/reset.py` | Stops any load and leaves 1 pod, between demos |
| `docs/demo.md` | Step-by-step live demo ([español](docs/demo.es.md)) |

## Getting started (minikube)

Requirements: Docker, minikube, kubectl, helm, Python 3.11+ with `app/requirements.txt` ([new machine](docs/demo.md#1-a-new-machine-from-zero-about-45-minutes-do-it-before-the-class)).

```bash
scripts/setup.sh                 # minikube, metrics-server, Prometheus, Traefik, DynamoDB Local, catalog-service, HPA
cd app
python3 -m aegis.calibrate       # once per environment, ~17 min: measures C and T
python3 -m aegis.actuator        # Aegis, with its dashboard on http://localhost:8080
```

- No cluster: `cd app && python3 -m aegis.replay --speed 5` replays a recorded run.
- Fast machine: `scripts/setup.sh --pod-cpu 60m` keeps C at 20–30 req/s. `--build` rebuilds the service image; `--hpa baseline` runs without Aegis.
- Aegis flags: `--dry-run`, `--log file.ndjson`.
- In the cluster: `scripts/setup.sh --aegis [--hpa aegis-metric]` ([docs/deployment.md](docs/deployment.md)).
- Unit tests: `cd app && python3 -m pytest`.

## Experiments

The experiments (runs, raw data, charts, statistical analysis and their tooling) live in the [`tests` branch](https://github.com/xDiegoAGG/Aegis/tree/tests/), so `main` keeps only Aegis and what deploys it. `git checkout tests` brings them back.

Randomized complete block design, 2026-11-05: 3 autoscalers × 3 loads × 6 blocks = 54 runs in a random order registered before the first run ([design](https://github.com/xDiegoAGG/Aegis/tree/tests/docs/experiments/design.md), [results](https://github.com/xDiegoAGG/Aegis/tree/tests/docs/experiments/results.md)). Failed requests, mean of 6 runs:

| Load | Aegis | Default HPA (CPU 70%) | Tuned HPA (CPU 50%, 60 s down) |
|---|---|---|---|
| Ramp | **1.9%** | 16.9% ✓ | 15.4% ✓ |
| Spike | **5.6%** | 26.7% ✓ | 24.9% ✓ |
| Waves | **1.4%** | 3.7% (not significant) | 7.1% ✓ |

✓ = Aegis lower, Holm-corrected p < 0.05 (5 of 6 pre-registered contrasts). Aegis was degraded half the time or less on ramps and spikes and used the same or fewer pod-minutes, except on the spike against the tuned HPA.

## More documentation

- [Dashboard](docs/dashboard.md)
- [Deployment in the cluster, metrics, Custom Metrics API and HPA](docs/deployment.md)
- [Workload capacity, L and T_d](docs/capacity.md)
- [Operating boundaries, limitations and threats to validity](docs/limitations.md)
- [Business case, with the economic model step by step](docs/business-case.md) (Spanish)
- [Experimental methodology](https://github.com/xDiegoAGG/Aegis/tree/tests/docs/experiments/methodology.md) (`tests` branch)
- [References](docs/references.md)
