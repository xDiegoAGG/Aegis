# Dashboard

Plain HTML/JS served by Aegis on port 8080, no CDN.

```bash
cd app
python3 -m aegis.actuator                 # live: http://localhost:8080 (opens on the live view when there are no recorded runs)
python3 -m aegis.replay --speed 5         # a recorded run (ramp with Aegis, block 3), no cluster needed
python3 -m aegis.replay ../docs/tests/spike-aegis/data/run-2-aegis.ndjson --speed 10 --loop
```

In the cluster: `kubectl port-forward -n aegis-system svc/aegis 8080`. `--port` changes the port, `--no-server` disables it.

**Results tab** (the default page): the answer to "does Aegis work?", from the 54-run block campaign.

1. **The answer as the heading**, computed from the registered verdicts ("with Aegis between 4.4 and 9.1 times fewer requests failed…"), and under it in how many of the 6 comparisons that held and the exception.
2. **One row per autoscaler, grouped by load** (ramp, spike, waves) on one shared scale: the 6 runs as dots, the mean as a tick and a bold number, and on each HPA row the verdict against Aegis in words with its p-value. A picker switches the metric (failed requests, seconds degraded, pod-minutes, when the 2nd pod is requested); "Show as a table" gives every mean and range.
3. **Three findings** in plain words, each computed from the data: it does not only anticipate, it does not cost more, how it was measured.
4. **Explore the runs:** up to 3 runs on one axis with a summary table and their charts, design runs first and the October campaign folded away; then the calibration curves.

**One run tab** ("Live" when Aegis runs on a cluster), in the order a viewer needs it:

1. **Aegis against the HPAs** (replay only): the replayed run next to the median run of each HPA with the same load, on one scale, failed traffic in red; under them the campaign means.
2. **At this moment:** a sentence from the last cycle ("Los pods no alcanzan", "Al límite hasta que el pod 2 esté listo"…) and one tank per pod, all filled to the same level because Traefik splits the traffic evenly; the dashed line is the level expected in T + lag.
3. **Last minutes:** traffic against the capacity of the Ready pods, with the projection into the next T + lag seconds and a legend.
4. **What Aegis did:** each decision as a sentence with its numbers.
5. **How Aegis decides** (collapsed): the formula with the cycle's values, forecast vs actual, risk, pods, P95, σ and m; parameters and the raw cycles. Titles and notes take the horizon and thresholds from the running configuration.

When replaying, a selector at the top switches between the saved Aegis runs and describes the load; it calls `POST /api/replay {"test": ..., "run": N}`. `?lang=es` or `?lang=en` picks the language; `#live` opens the run view and `#how` its technical section.

**Colors**, one meaning each, the same as the report charts and checked for color blindness in light and dark: Aegis blue, default HPA orange, tuned HPA aqua, traffic and its projection neutral (the projection dashed), red only for failures. Text is never set in a series color.

| Endpoint | Content |
|---|---|
| `/api/state?since=<unix>` | parameters and cycles after `since` (2 h in memory) |
| `/api/tests` | run summaries and calibration |
| `/api/design` | the analysis of the experiment design (`docs/tests/design-results.json`) |
| `/api/tests/<test>/<run>` | rows, summary and Aegis log of one run |
| `/metrics` | Prometheus metrics ([list](deployment.md#metrics)) |
| `POST /api/replay` | replay only: switch to another saved run |
| `/healthz`, `/readyz` | probes |

Light/dark and ES/EN toggles in the header. Font: Chivo (OFL), bundled in `dashboard/fonts/`.
