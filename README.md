# Aegis

Preventive horizontal scaling mechanism for Kubernetes services.

Aegis estimates the probability of latency degradation within a short prediction horizon ($T_p$) and publishes that risk as a signal for the standard Kubernetes Horizontal Pod Autoscaler (HPA). By scaling capacity ahead of demand spikes, Aegis closes the 1.5 to 3-minute reactivity lag inherent in traditional autoscalers without requiring expensive 24/7 overprovisioning.

---

## Getting started (minikube)

Requirements: `minikube`, `kubectl`, `helm` and `python3` (with the packages in `app/requirements.txt`).

```bash
scripts/setup.sh
```

This starts minikube if needed and installs or repairs everything: `metrics-server`, Prometheus (`kube-prometheus-stack`), DynamoDB Local, the `tb_books` table (seeded by a Kubernetes Job), `catalog-service` and its HPA. It is safe to run many times and ends by checking the environment.

| Option | What it does |
|---|---|
| `--hpa aegis` | HPA for running with Aegis: CPU at 95%, no scale-down window (default) |
| `--hpa baseline` | Plain HPA (CPU 70%), to run tests without Aegis |
| `--build` | Rebuild the `catalog-service` image after changing its code |

To only check the environment, without changing anything:

```bash
python3 scripts/check_env.py
```

To run Aegis from your machine, keep a Prometheus tunnel open:

```bash
kubectl -n monitoring port-forward svc/prometheus-kube-prometheus-prometheus 9090:9090
```

Then, from `app/`, calibrate once per environment and start the loop:

```bash
cd app
AEGIS_PROMETHEUS_URL=http://localhost:9090 python3 -m aegis.calibrate   # ~20 min, Aegis must not be running
AEGIS_PROMETHEUS_URL=http://localhost:9090 python3 -m aegis.actuator
```

The calibration measures C (requests per second one pod handles before it degrades) and T (time from asking for a pod until it is Ready) and saves them in the ConfigMap `aegis-calibration`. Aegis does not start without it, and warns when the environment changed since it was measured (image, CPU or memory limit, node type). What counts as degraded is set in `app/config.yaml` (`degradation`: P95 above 1 s for 15 s).

---

## Documentation

* **Business Case & ROI:** [docs/business_case.md](docs/business_case.md)
  Executive pitch, FinOps analysis, ROI formulas, and industry evidence on the cost of latency.
* **Architecture Overview:** [docs/architecture/overview.md](docs/architecture/overview.md)
  System design, responsibility boundaries, Aegis internal pipeline, and key parameters ($L$, $T_d$, $T_p$, $\sigma$).
* **Experimental Methodology:** [docs/experiments/methodology.md](docs/experiments/methodology.md)
  Validation protocol, hypotheses (H1 to H4), evaluation phases, and test workloads (MyBookstore).
* **Project Bibliography:** [docs/references.md](docs/references.md)
  Foundational academic literature and Kubernetes documentation.
