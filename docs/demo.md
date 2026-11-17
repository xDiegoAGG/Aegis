# Live demo

[Español](demo.es.md)

Aegis runs on EKS and the monitor is an S3 website. Everything is shown in the browser: a button sends real traffic (k6 inside the cluster), and the four charts show Aegis asking for pods **before** they run short and giving them back after. Three demos: Ramp (~4 min), Waves (~9 min) and Spike (~3 min). If AWS fails, the same demo runs on minikube (section 7).

## 1. Before the class (~45 min)

Follow [aws.md](aws.md): credentials, `scripts/eks_up.sh`, `scripts/push_images.sh`, `scripts/setup.sh --aegis --registry …`, calibration and `scripts/deploy_monitor.sh`. Then check:

```bash
python3 scripts/check_env.py      # every line OK, with C and T
python3 scripts/reset.py          # no load, 1 pod
kubectl get secret aegis-load-key -n aegis-system -o jsonpath='{.data.key}' | base64 -d    # the load key
```

`deploy_monitor.sh` prints the monitor URL. Open it, paste the key in **Load key** and check that the header says **Live**. Restarting Aegis empties the charts; that is normal.

## 2. What is on the screen

| Part | What to say |
|---|---|
| Cards | Demand now, risk, pods Ready / requested, P95, C and T (measured by the calibration), σ (learned live), last decision |
| Requests per second | Blue: demand. Violet: what Aegis expects T + 20 s ahead. Gray steps: what the Ready pods serve (C × pods) |
| Risk | Probability of running short **with the pods Aegis already asked for**. At 70% it asks for one more; then the risk drops to ~0 because the formula already counts that pod |
| Pods | Blue: what Aegis asks for (HPA minReplicas). Black: Ready. Orange dashed: what the HPA alone would want from CPU |
| Latency P95 | 95% of the requests are faster than this; above L = 1 s the service counts as slow. Measured over 30 s, so it shows problems a few seconds late |

Times are Colombia time (UTC−5), the same as the classroom clock.

## 3. Demo 1: Ramp

Press **Ramp**. Traffic climbs from 0.2 C to 2.1 C in 2 minutes, stays 1 minute and goes down (on EKS with C = 16: 3 → 34 req/s).

| When (s after the button) | What you see | What to say |
|---|---|---|
| 0–30 | demand low, risk 0% | One pod is enough |
| 30–70 | the violet line climbs ahead of the blue one | Aegis extrapolates the trend T + 20 s ahead |
| ~70 | risk crosses 70%, mark ▲2, blue step to 2 | It asks for the 2nd pod while the traffic is still **under** one pod's capacity |
| ~90 | black step to 2, gray capacity doubles | The pod is Ready about T = 17 s later, right when it is needed |
| ~130 | ▲3 | Near 2 C two pods are not enough: it asks for the third |
| ~250–300 | demand falls, ▼1 | Aegis gives the pods back after 15–60 s of low risk |

Rehearsal on EKS (2026-11-17): 2nd pod asked at 71 s with 10 req/s, 3rd at 131 s, back to 1 pod after the load.

## 4. Demo 2: Waves

Wait for 1 pod (the pods card shows 1 / 1), then press **Waves**: a wave to 1.25 C (needs 2 pods), 105 s low, a wave to 2.1 C (needs 3 pods), 120 s low. About 9 minutes.

What to say: Aegis scales up on each climb and **back down** between the waves, so it does not keep pods it does not need.

## 5. Demo 3: Spike

Press **Spike**: from 0.2 C to 1.9 C in 5 s. Nothing announces it, so Aegis cannot anticipate: it reacts in the next cycles, which is still sooner than the HPA (its orange line). This is the honest limit of a trend projection.

## 6. If something goes wrong

| Symptom | Fix |
|---|---|
| Header says **Aegis unreachable** | `kubectl get pods -n aegis-system`; `kubectl logs -n aegis-system deploy/aegis` |
| Buttons disabled, "no load key" | Run `scripts/setup.sh --aegis --registry …` again (it creates the Secret) |
| "Wrong key" | Paste the key again (section 1) |
| "Another load is still running" | Press **Stop**, or `python3 scripts/reset.py` |
| Aegis starts with more than 1 pod | `python3 scripts/reset.py`, then `kubectl rollout restart -n aegis-system deploy/aegis` |
| The browser blocks the API (CORS) | `scripts/deploy_monitor.sh` again: it allows the site URL |
| `/api/books` returns 500 | `scripts/setup.sh --aegis --registry …` (it seeds the table again) |
| AWS credentials expired | Copy the new ones (aws.md) and `aws eks update-kubeconfig --name aegis --region us-east-1` |

## 7. Plan B: minikube on this PC

The same monitor and buttons, without AWS. It needs a machine with at least 4 CPU threads and 8 GB of RAM.

```bash
git clone https://github.com/xDiegoAGG/Aegis.git && cd Aegis
python3 -m venv .venv && source .venv/bin/activate
pip install -r app/requirements.txt
scripts/setup.sh --aegis                         # minikube, Prometheus, Traefik, DynamoDB, service, HPA, Aegis (~15 min)
cd app && python3 -m aegis.calibrate && cd ..    # C and T, ~17 min, once per machine
scripts/setup.sh --aegis                         # now Aegis starts with the calibration
kubectl port-forward -n aegis-system svc/aegis 8080 &
cd monitor && npm install && npm run dev         # http://localhost:5173
```

Tools: Docker, minikube v1.39.0, kubectl, Helm v3, Python 3.11+, Node.js 20+. If C is outside 20–30 req/s, change the pod CPU (`scripts/setup.sh --aegis --pod-cpu 60m`, new CPU ≈ tested CPU × wanted C ÷ measured C) and calibrate again. More memory for minikube: `MINIKUBE_CPUS=4 MINIKUBE_MEMORY=6g scripts/setup.sh --aegis`.

## 8. After the class

```bash
scripts/eks_down.sh       # deletes the cluster and its load balancer
```
