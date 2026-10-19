# Aegis tests

Log of every test run in the project. Each test has its own document with what was done, when, the results and its chart. Raw data (CSV) and charts (PNG) live in [`data/`](data/).

All times are in **UTC** (local time = UTC − 5).

| # | Test | Date | Purpose | Key result |
|---|---|---|---|---|
| 01 | [Capacity of one pod](01-capacity-calibration.md) | 2026-09-27 | Measure $C$ | P95 jumps from ~0.3 s to 5 s around 18–20 req/s → **C = 18** |
| 02 | [Steps below capacity](02-step-load-calibration.md) | 2026-09-27 | Confirm $C$ and measure $\sigma$ | 5, 10 and 14 req/s with no degradation |
| 03 | [Startup time](03-startup-time-calibration.md) | 2026-09-27 | Measure $T$ | 13, 15, 12 and 11 s → **T = 13** |
| 04 | [Baseline HPA, without Aegis](04-hpa-baseline.md) | 2026-09-28 | "Before" comparison | The HPA scales **95 s after** latency breaks |
| 05 | [Collector](05-collector.md) | 2026-09-28 | Test `collector.py` | Follows the steps and survives Prometheus being down |
| 06 | [Risk calculator, synthetic scenarios](06-risk-synthetic.md) | 2026-09-28 | Test `risk.py` without real traffic | Every case gives the expected result |
| 07 | [Risk calculator, live](07-risk-live.md) | 2026-09-28 | Test `risk.py` with real traffic | Risk crosses 70% **65 s before** latency breaks |
| 08 | [Decision engine, synthetic scenarios](08-decision-synthetic.md) | 2026-09-28 | Test `decision.py` without real traffic | Right orders in all 8 scenarios, no flapping |
| 09 | [Decision engine, replayed on real data](09-decision-replay.md) | 2026-09-28 | See what Aegis would have decided in test 07 | Scale-up **65 s before** latency breaks; scale-down 60 s after traffic ends |
| 10 | [Actuator, manual test](10-actuator-manual.md) | 2026-10-13 | Test `actuator.py` against the real HPA | `minReplicas` 1 → 3 creates pods at once; the HPA delayed scale-down ~5 min, fixed with the Aegis HPA (~1 s) |
| 11 | [Aegis live](11-aegis-live.md) | 2026-10-14 | "After" comparison: same ramp as 04, Aegis scaling | Scale-up **26 s before** latency breaks, 0% errors (vs 6.15%); latency still breaks because keep-alive connections stay on the old pod |
| 12 | [Baseline HPA, one connection per request](12-hpa-baseline-no-reuse.md) | 2026-10-14 | Repeat 04 with the load-balancing fix | Traffic is split evenly, but 1 pod handles ~28 req/s without breaking: **C must be measured again** |
| 13 | [Reproducible environment](13-environment-setup.md) | 2026-10-15 | Test `scripts/setup.sh` and `check_env.py` | One command restores everything after the machine was off; the table survives a minikube restart |
| 14 | [Automatic calibration of C and T](14-automatic-calibration.md) | 2026-10-19 | Test `aegis.calibrate` | **C = 32**, **T = 14** with no manual steps; the service's own P95 does not see saturation |
| 15 | [Sigma calculated live](15-sigma-live.md) | 2026-10-19 | Replace the fixed σ = 2 | Live σ stays at 1–3 req/s; same decisions in ramps, and it would have scaled in time in test 14 where σ = 2 never did |

## How each artifact is produced

Everything needs the Prometheus tunnel open:

```
kubectl -n monitoring port-forward svc/prometheus-kube-prometheus-prometheus 9090:9090
```

| Script | What it does |
|---|---|
| `scripts/export_run.py START END output` | Exports req/s, P95 and replicas of a run to `output.csv` |
| `scripts/plot_run.py input.csv output.png [--title ...] [HH:MM:SS=event ...]` | 3-panel chart (traffic, latency, replicas) |
| `scripts/plot_startup.py START END output.png` | Chart of the startup time of each new pod |
| `scripts/plot_pods.py START END output [--title ...]` | Requests per second and Ready state of each pod, to `output.csv` and `output.png` |
| `scripts/plot_calibration.py calibration.json output.png` | Chart of a calibration saved with `python3 -m aegis.calibrate --output calibration.json` |
| `scripts/replay_risk.py START END output [--capacity C] [--startup T] [--sigma S]` | Feeds a run's data through the risk calculator and the decision engine (simulated) and saves `output.csv`. C and T come from the cluster calibration unless given (runs before test 14 used C = 18, T = 13); σ is calculated live unless `--sigma` fixes it (runs before test 15 used 2) |
| `scripts/plot_risk.py input.csv output.png [--title ...] [HH:MM:SS=event ...]` | 4-panel chart (traffic, latency, risk, replicas; plus the simulated Aegis target if present) |

Prometheus keeps 10 days of data, so a run can be exported and plotted later, as long as it is less than 10 days old.
