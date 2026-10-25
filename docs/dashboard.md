# Dashboard

Plain HTML/JS served by Aegis on port 8080, no CDN.

```bash
cd app
python3 -m aegis.actuator                 # live: http://localhost:8080
python3 -m aegis.replay --speed 5         # a recorded run (test 1, run 4), no cluster needed
python3 -m aegis.replay ../docs/tests/test1-linear-ramp/data/run-4-aegis.ndjson --speed 10 --loop
```

In the cluster: `kubectl port-forward -n aegis-system svc/aegis 8080`. `--port` changes the port, `--no-server` disables it.

**Live tab**, in the order a viewer needs it:

1. **Do the pods keep up?** A sentence from the last cycle ("Los pods no alcanzan", "Al límite hasta que el pod 2 esté listo"…) and one tank per pod, all filled to the same level because Traefik splits the traffic evenly. Red water and "req/s sin atender" when traffic exceeds the Ready pods; the amber line is the level expected in T + lag.
2. **Aegis against the HPA alone** (replay only): for the ramp and the spike, the replayed run next to the median HPA-only run with the same load: when each asked for the 2nd pod, failed requests, seconds slow and pod-minutes. The history chart adds the HPA-only capacity at the same moment of the load as a grey line.
3. **Last minutes:** traffic against the capacity of the Ready pods, with the projection into the next T + lag seconds.
4. **What Aegis did:** each decision as a sentence with its numbers.
5. **How Aegis decides** (collapsed): the formula with the cycle's values, forecast vs actual, risk, pods, P95, σ and m, each with one line explaining it; parameters and the raw cycles.

When replaying, a selector at the top switches between the saved Aegis runs (HPA-only runs have no Aegis log to replay) and says what traffic that test has; it calls `POST /api/replay {"test": ..., "run": N}`. `?lang=es` or `?lang=en` picks the language; `#how` opens the technical section.

**Experiments tab:** up to 3 saved runs on one axis, a summary table, their charts, and the calibration curves.

| Endpoint | Content |
|---|---|
| `/api/state?since=<unix>` | parameters and cycles after `since` (2 h in memory) |
| `/api/tests` | run summaries and calibration |
| `/api/tests/<test>/<run>` | rows, summary and Aegis log of one run |
| `/metrics` | Prometheus metrics ([list](deployment.md#metrics)) |
| `POST /api/replay` | replay only: switch to another saved run |
| `/healthz`, `/readyz` | probes |

Light/dark and ES/EN toggles in the header. Font: Chivo (OFL), bundled in `dashboard/fonts/`.
