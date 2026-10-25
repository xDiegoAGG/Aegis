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

1. **Do the pods keep up?** A sentence from the last cycle ("Los pods no alcanzan", "Al límite mientras arranca el pod 2"…) and one tank per pod, all filled to the same level because Traefik splits the traffic evenly. Red water and "req/s sin atender" when traffic exceeds the Ready pods; the amber line is the level expected in T + lag.
2. **Last minutes:** traffic against the capacity of the Ready pods, with the projection into the next T + lag seconds.
3. **What Aegis did:** each decision as a sentence with its numbers.
4. **How Aegis decides** (collapsed): the formula with the cycle's values, forecast vs actual, risk, pods, P95, σ and m, each with one line explaining it; parameters and the raw cycles.

`?lang=es` or `?lang=en` picks the language; `#how` opens the technical section.

**Experiments tab:** up to 3 saved runs on one axis, a summary table, their charts, and the calibration curves.

| Endpoint | Content |
|---|---|
| `/api/state?since=<unix>` | parameters and cycles after `since` (2 h in memory) |
| `/api/tests` | run summaries and calibration |
| `/api/tests/<test>/<run>` | rows, summary and Aegis log of one run |
| `/metrics` | Prometheus metrics ([list](deployment.md#metrics)) |
| `/healthz`, `/readyz` | probes |

Light/dark and ES/EN toggles in the header. Font: Chivo (OFL), bundled in `dashboard/fonts/`.
