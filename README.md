# Aegis

Preventive horizontal scaling for Kubernetes services.

The Horizontal Pod Autoscaler (HPA) reacts when the CPU is already high, and a new pod still needs some seconds to be ready: by then the service is slow. Aegis projects the traffic of the next seconds, calculates the probability of going over the capacity of the pods, and raises `minReplicas` of the HPA **before** that happens. When the traffic drops, it lowers it again.

Every 5 seconds:

```
Prometheus ──► demand r ──► projection p = r + m·(T + lag) ──► risk = Φ((p − C·N) / σ) ──► 70% up / 30% for 60 s down ──► HPA minReplicas
```

- **C** (requests per second one pod can serve) and **T** (time until a requested pod is Ready) are measured by an automatic calibration, not written by hand.
- **σ** (how wrong the projection is) is learned live from the projection's own errors.
- Where each formula comes from: [docs/formulas.md](docs/formulas.md) ([español](docs/formulas.es.md)).

## Repository

| Path | What it is |
|---|---|
| `app/aegis/collector.py` | Reads demand, latency and Ready pods from Prometheus |
| `app/aegis/risk.py` | Projection, live σ and risk |
| `app/aegis/decision.py` | Scale-up and scale-down rules |
| `app/aegis/actuator.py` | Main loop: applies the decisions to the HPA `minReplicas` |
| `app/aegis/calibrate.py`, `calibration.py` | Measure C and T; save and read them in the cluster |
| `app/config.yaml` | Thresholds, queries and calibration settings |
| `services/catalog-service/`, `shared/proto/` | The service Aegis protects (from MyBookstore): HTTP and gRPC over DynamoDB |
| `kubernetes/catalog-service/`, `dynamodb/` | The service, its Ingress and ServiceMonitor; DynamoDB Local and the table seed |
| `kubernetes/hpa/` | `aegis.yaml` (used with Aegis) and `baseline.yaml` (plain HPA, CPU 70%) |
| `kubernetes/load/` | The two k6 traffic profiles: `linear.yaml` and `fluctuating.yaml` |
| `kubernetes/helm/` | Values for Prometheus and Traefik |
| `scripts/setup.sh`, `scripts/check_env.py` | Bring up and check the whole environment |
| `scripts/experiments/` | Run the tests (`run.py`), draw them (`report.py`), reset between runs (`reset.py`) |
| `docs/tests/` | The tests, their charts and data ([summary](docs/tests/README.md)) |
| `docs/demo.md` | Step-by-step live demo ([español](docs/demo.es.md)) |

## Getting started (minikube)

Requirements: `minikube`, `kubectl`, `helm` and `python3` with the packages in `app/requirements.txt`.

```bash
scripts/setup.sh                 # minikube, metrics-server, Prometheus, Traefik, DynamoDB Local, catalog-service, HPA
cd app
python3 -m aegis.calibrate       # once per environment, ~17 min: measures C and T
python3 -m aegis.actuator        # Aegis
```

No tunnel is needed: Aegis reaches Prometheus through the Kubernetes API server. `scripts/setup.sh --build` rebuilds the service image after changing its code; `--hpa baseline` applies the plain HPA (CPU 70%) to run without Aegis. Aegis can also run with `--dry-run` (decides without changing the HPA) and `--log file.ndjson` (one JSON line per cycle).

## Tests

```bash
cd scripts/experiments
./run_all.sh                       # the three tests, 5 runs each (~2 h); runs already done are skipped
python3 run.py test1-linear-ramp   # or one test only
python3 report.py                  # charts and tables again from the saved data
```

| Test | What it shows |
|---|---|
| [Test 1: linear ramp](docs/tests/test1-linear-ramp/) | Aegis asks for the pod before the traffic goes over one pod's capacity |
| [Test 2: fluctuating traffic](docs/tests/test2-fluctuating/) | Aegis scales up on each wave and down when the traffic drops |
| [Test 3: HPA only](docs/tests/test3-hpa-baseline/) | The same ramp as test 1 without Aegis: the HPA scales late |

## More documentation

- [Business case](docs/business_case.md)
- [Experimental methodology](docs/experiments/methodology.md)
- [References](docs/references.md)
