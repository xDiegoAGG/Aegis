# Live demo

Two console demos (~6 and ~10 min): a linear ramp, where Aegis asks for a pod **before** one pod is exceeded, and fluctuating traffic, where it scales up on each wave and **back down** after it.

## 1. A new machine, from zero (about 45 minutes, do it before the class)

Tested on Kali Linux; the commands are for Ubuntu/Debian on amd64.

**Hardware**: at least 4 CPU threads and 8 GB of RAM (minikube takes 2 CPUs and 4 GB), 20 GB free disk, internet.

| Tool | Version used |
|---|---|
| Docker | 29.9.0 |
| minikube | v1.39.0 (Kubernetes v1.37.0) |
| kubectl | v1.37.1 |
| Helm | v3.22.0 |
| Python | 3.13 (3.11 or newer works) |

### 1.1 Install the tools (~10 min)

```bash
sudo apt update
sudo apt install -y git curl python3 python3-venv python3-pip

# Docker. On Kali use instead: sudo apt install -y docker.io
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker                      # or log out and in again
docker run --rm hello-world        # must print "Hello from Docker!"

# kubectl
curl -LO https://dl.k8s.io/release/v1.37.1/bin/linux/amd64/kubectl
sudo install -m 0755 kubectl /usr/local/bin/kubectl && rm kubectl

# minikube
curl -LO https://github.com/kubernetes/minikube/releases/download/v1.39.0/minikube-linux-amd64
sudo install minikube-linux-amd64 /usr/local/bin/minikube && rm minikube-linux-amd64

# Helm
curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash -s -- --version v3.22.0
```

On macOS: Docker Desktop and `brew install git python kubectl minikube helm`. On Windows: WSL2 with Ubuntu and the Linux commands inside it. Neither was tested.

### 1.2 Get the project (~2 min)

```bash
git clone https://github.com/xDiegoAGG/Aegis.git
cd Aegis
python3 -m venv .venv
source .venv/bin/activate
pip install -r scripts/experiments/requirements.txt
```

**Every new terminal** needs these two lines first: `cd Aegis` and `source .venv/bin/activate`.

### 1.3 Bring up the environment (~15 min the first time)

```bash
scripts/setup.sh
```

It must end with `Environment ready`; `Aegis calibration - not calibrated yet` is expected on a new machine. More resources for minikube (first run only): `MINIKUBE_CPUS=4 MINIKUBE_MEMORY=6g scripts/setup.sh`.

### 1.4 Calibrate (~17 min, once per machine)

Nothing else may run meanwhile.

```bash
cd app
python3 -m aegis.calibrate
cd ..
```

It ends with `Saved in ConfigMap aegis-calibration: C=… req/s, T=… s`. The traffic profiles expect C between 20 and 30 req/s, and the timings below are for C ≈ 24. If C is outside that range (or it says `no degradation up to 80 req/s`), change the pod CPU with new CPU ≈ tested CPU × (wanted C ÷ measured C), for example `scripts/setup.sh --pod-cpu 60m`, and calibrate again. A new cluster starts at 200m; this PC uses 200m (C = 24).

### 1.5 Leave it at rest

```bash
python3 scripts/check_env.py           # every line OK, and the calibration
python3 scripts/experiments/reset.py   # 1 pod, no traffic
```

After a reboot, `scripts/setup.sh` brings everything back; the calibration is kept.

## 2. Terminals

Three terminals in the repository root, each with `source .venv/bin/activate`.

Right before the demo, check that everything is still up (after a reboot it brings minikube back):

```bash
scripts/setup.sh
python3 scripts/experiments/reset.py
```

**Terminal 1, Aegis** (leave it running for both demos):

```bash
cd app
python3 -m aegis.actuator
```

It uses the default `min_replicas` mode: Aegis raises `minReplicas` of the HPA. The metric mode is only an experiment (test 8), not used in the demo.

You should see `Calibration from …: C=… req/s, T=… s`, then one line every 5 s:

```
demand=0.0 projected=0.0 sigma=2 risk=0.0% ready=1 | HOLD 1 -> 1 (already at min_replicas)
```

| Field | Meaning |
|---|---|
| `demand` | req/s arriving at the entrance (Traefik), also the ones waiting |
| `projected` | the traffic Aegis expects T + 20 s from now |
| `sigma` | how wrong the projections have been lately (req/s) |
| `risk` | probability of going over the capacity of the pods already requested |
| `ready` | pods Ready now |
| `HOLD / SCALE_UP / SCALE_DOWN 1 -> 2` | the decision and the pods requested before and after |

Decisions are printed as `WARNING` so they stand out.

**Browser**: http://localhost:8080 shows the same values live, with the formula of the last cycle and every scale event ([dashboard.md](dashboard.md)). If the cluster fails, `cd app && python3 -m aegis.replay --speed 3` plays a recorded run.

**Terminal 2, pods and HPA**:

```bash
watch -n 2 "kubectl get hpa catalog-service; echo; kubectl get pods -l app=catalog-service"
```

**Terminal 3, the traffic**: used in each demo below.

## 3. Demo 1: linear ramp

The traffic goes from 5 to 50 req/s in 2 minutes, stays 1 minute at 50 and goes down. One pod can serve C ≈ 24 req/s (development machine): k6 passes that at second 81.

In terminal 3:

```bash
kubectl apply -f kubernetes/load/linear.yaml
kubectl logs -f job/load-linear
```

| When (s since k6 started) | Where | What you see | What to say |
|---|---|---|---|
| 0–30 | T1 | `demand` ≈ 5, risk 0% | One pod is enough |
| 30–60 | T1 | `demand` climbs, `projected` is ahead of it | Aegis extrapolates the trend T + 20 s ahead |
| ~65–75 | T1 | `SCALE_UP 1 -> 2` with risk ≥ 70% | The traffic is still under C; the projection is not |
| ~80–90 | T2 | a second pod goes from `0/1` to `1/1` | The new pod is Ready around second 81, when the traffic passes C |
| ~110–150 | T1 | `SCALE_UP 2 -> 3` | Near 50 req/s two pods (2C ≈ 48) are not enough: it asks for a third one |
| 240 | T3 | k6 summary: `http_req_failed` of a few % at most (2.5% on average in test 1) | With the HPA alone the same ramp fails ~37% (test 3) |
| ~285–330 | T1 | `SCALE_DOWN 3 -> 2`, then `2 -> 1` | One pod less at a time, each after 60 s of low risk |

When it ends (Ctrl+C in terminal 3; the Job keeps its pod 10 min, that is normal):

```bash
python3 scripts/experiments/reset.py
```

Leave Aegis running in terminal 1.

## 4. Demo 2: fluctuating traffic

Two waves that climb like the ramp, 560 s in total: 30 s at 5 req/s, a wave to 30 req/s (needs 2 pods), 105 s at 5 req/s, a wave to 50 req/s (needs 3 pods, 2C ≈ 48), 120 s at 5 req/s. Times from test 2.

In terminal 3:

```bash
kubectl apply -f kubernetes/load/fluctuating.yaml
kubectl logs -f job/load-fluctuating
```

| When (s) | What you see | What to say |
|---|---|---|
| ~75 | `SCALE_UP 1 -> 2` during the first climb | Same as demo 1: before the wave passes C (~79 s) |
| 95–140 | traffic flat at 30, 2 pods | Two pods are enough for this wave |
| ~215–220 | `SCALE_DOWN 2 -> 1` while traffic is at 5 | **Aegis gives the pod back** when it is not needed, after 60 s of low risk |
| ~305 | `SCALE_UP 1 -> 2` on the second climb | The second wave starts: it asks again before C |
| ~365 | `SCALE_UP 2 -> 3` | The second wave goes over 2C: it asks for the third pod |
| ~500–570 | `SCALE_DOWN 3 -> 2`, then `2 -> 1` | It goes back to 1 pod, one step at a time |
| 560 | T3: k6 summary | Under 1% failed (0.32–0.97% in test 2) |

When it ends:

```bash
python3 scripts/experiments/reset.py
```

## 5. The HPA alone (show the charts, not live)

Running it live takes ~15 minutes. Show `docs/tests/test3-hpa-baseline/` instead, or the *Experiments* tab of the dashboard with tests 1 and 3 side by side.

To run it live anyway: stop Aegis (Ctrl+C in terminal 1), then

```bash
kubectl apply -f kubernetes/hpa/baseline.yaml
kubectl apply -f kubernetes/load/linear.yaml
```

and at the end `python3 scripts/experiments/reset.py` (it puts the Aegis HPA back).

## 6. If something goes wrong

| Symptom | Fix |
|---|---|
| `permission denied ... docker.sock` | The user is not in the `docker` group yet: `sudo usermod -aG docker $USER`, then log out and in |
| `pip install` says `externally-managed-environment` | The virtual environment is not active: `source .venv/bin/activate` |
| `ModuleNotFoundError: No module named 'kubernetes'` (or `yaml`) | Same: activate `.venv` in that terminal |
| `minikube start` fails for memory | Give it less: `MINIKUBE_MEMORY=3g scripts/setup.sh`, or close other programs |
| `setup.sh` stops with a timeout while downloading images | Slow internet: run `scripts/setup.sh` again, it continues where it stopped |
| Aegis says `No calibration found` | `cd app && python3 -m aegis.calibrate` |
| `demand=-` and warnings `Prometheus did not answer` | Prometheus is restarting; Aegis keeps running and recovers by itself. `python3 scripts/check_env.py` |
| `kubectl apply` says the Job is immutable | A previous Job is still there: `python3 scripts/experiments/reset.py` |
| `/api/books` returns 500 | `scripts/setup.sh` (it seeds the table again) |
| Aegis starts with more than 1 pod | Stop it, `python3 scripts/experiments/reset.py`, start it again |
| `Address already in use` (port 8080) | Another Aegis or replay is still running: `pkill -f aegis.replay` (or stop the other Aegis), or start with `--port 8081` |
