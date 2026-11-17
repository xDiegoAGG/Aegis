# Aegis monitor

[Español](README.es.md)

Live web monitor of Aegis, in React (Vite + Recharts). It reads `GET /api/state` every 2 s and shows only what is happening now:

- **Cards:** demand, risk, Ready/requested pods, P95, C and T, σ and the last decision.
- **Send traffic:** Ramp, Spike and Waves start a real k6 load inside the cluster (`POST /api/load`); Stop ends it. One load at a time, each with a time limit, and only with the load key.
- **Four charts** on the same axis, in Colombia time (UTC−5) whatever the zone of the computer: requests per second (demand, projection and capacity of the Ready pods), risk (70% and 30% lines, ▲/▼ marks at each decision), pods (requested by Aegis, Ready, wanted by the HPA) and P95 latency (line at L). Window of 5, 15 or 30 minutes.
- **Decisions:** the last scale-ups and scale-downs with their reason.

## Run it locally

Aegis must be running (`cd app && python3 -m aegis.actuator`, or in the cluster with `kubectl port-forward -n aegis-system svc/aegis 8080`).

```bash
cd monitor
npm install
npm run dev          # http://localhost:5173, /api goes to http://localhost:8080
npm test             # unit tests (Colombia time, series, load client)
```

`AEGIS_DEV_API=http://host:port npm run dev` points the development proxy somewhere else.

The buttons need the key of the cluster:

```bash
kubectl get secret aegis-load-key -n aegis-system -o jsonpath='{.data.key}' | base64 -d
```

A local Aegis takes it from `AEGIS_LOAD_KEY=... python3 -m aegis.actuator`. Without a key the buttons stay off.

## Build for S3

```bash
VITE_AEGIS_API_URL=http://<aegis-api-host>:8090 npm run build    # static files in dist/
```

The API must allow the origin of the site (`AEGIS_ALLOWED_ORIGIN`, set by `scripts/setup.sh --monitor-origin`). `scripts/deploy_monitor.sh` builds and uploads it.
