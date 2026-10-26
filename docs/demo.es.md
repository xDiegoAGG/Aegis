# Demo en vivo

Dos demos en consola (~6 y ~10 min): una rampa lineal, donde Aegis pide un pod **antes** de que se supere un pod, y tráfico fluctuante, donde sube en cada ola y **baja** después.

## 1. Una máquina nueva, desde cero (unos 45 minutos, hazlo antes de la clase)

Probado en Kali Linux; los comandos son para Ubuntu/Debian en amd64.

**Hardware**: al menos 4 hilos de CPU y 8 GB de RAM (minikube usa 2 CPUs y 4 GB), 20 GB libres en disco, internet.

| Herramienta | Versión usada |
|---|---|
| Docker | 29.9.0 |
| minikube | v1.39.0 (Kubernetes v1.37.0) |
| kubectl | v1.37.1 |
| Helm | v3.22.0 |
| Python | 3.13 (sirve 3.11 o más nuevo) |

### 1.1 Instalar las herramientas (~10 min)

```bash
sudo apt update
sudo apt install -y git curl python3 python3-venv python3-pip

# Docker. En Kali usa en cambio: sudo apt install -y docker.io
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker                      # o cierra sesión y vuelve a entrar
docker run --rm hello-world        # tiene que decir "Hello from Docker!"

# kubectl
curl -LO https://dl.k8s.io/release/v1.37.1/bin/linux/amd64/kubectl
sudo install -m 0755 kubectl /usr/local/bin/kubectl && rm kubectl

# minikube
curl -LO https://github.com/kubernetes/minikube/releases/download/v1.39.0/minikube-linux-amd64
sudo install minikube-linux-amd64 /usr/local/bin/minikube && rm minikube-linux-amd64

# Helm
curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash -s -- --version v3.22.0
```

En macOS: Docker Desktop y `brew install git python kubectl minikube helm`. En Windows: WSL2 con Ubuntu y los comandos de Linux adentro. Ninguno de los dos se probó.

### 1.2 Bajar el proyecto (~2 min)

```bash
git clone https://github.com/xDiegoAGG/Aegis.git
cd Aegis
python3 -m venv .venv
source .venv/bin/activate
pip install -r scripts/experiments/requirements.txt
```

**Cada terminal nueva** necesita primero estas dos líneas: `cd Aegis` y `source .venv/bin/activate`.

### 1.3 Levantar el entorno (~15 min la primera vez)

```bash
scripts/setup.sh
```

Tiene que terminar con `Environment ready`; `Aegis calibration - not calibrated yet` es lo esperado en una máquina nueva. Más recursos para minikube (solo la primera vez): `MINIKUBE_CPUS=4 MINIKUBE_MEMORY=6g scripts/setup.sh`.

### 1.4 Calibrar (~17 min, una vez por máquina)

No puede correr nada más mientras tanto.

```bash
cd app
python3 -m aegis.calibrate
cd ..
```

Termina con `Saved in ConfigMap aegis-calibration: C=… req/s, T=… s`. Los perfiles de tráfico esperan un C entre 20 y 30 req/s, y los tiempos de abajo son para C ≈ 24. Si C queda fuera de ese rango (o dice `no degradation up to 80 req/s`), cambia el CPU del pod con CPU nuevo ≈ CPU probado × (C buscado ÷ C medido), por ejemplo `scripts/setup.sh --pod-cpu 60m`, y calibra de nuevo. Un clúster nuevo arranca con 200m; este PC usa 200m (C = 24).

### 1.5 Dejarlo en reposo

```bash
python3 scripts/check_env.py           # todas las líneas OK, y la calibración
python3 scripts/experiments/reset.py   # 1 pod, sin tráfico
```

Tras reiniciar, `scripts/setup.sh` recupera todo; la calibración se conserva.

## 2. Terminales

Tres terminales en la raíz del repositorio, cada una con `source .venv/bin/activate`.

Justo antes de la demo, revisa que todo siga arriba (después de un reinicio, vuelve a levantar minikube):

```bash
scripts/setup.sh
python3 scripts/experiments/reset.py
```

**Terminal 1, Aegis** (déjala corriendo en las dos demos):

```bash
cd app
python3 -m aegis.actuator
```

Usa el modo `min_replicas`, que es el de siempre: Aegis sube `minReplicas` del HPA. El modo métrica es solo un experimento (prueba 8) y no se usa en la demo.

Debes ver `Calibration from …: C=… req/s, T=… s` y después una línea cada 5 s:

```
demand=0.0 projected=0.0 sigma=2 risk=0.0% ready=1 | HOLD 1 -> 1 (already at min_replicas)
```

| Campo | Significado |
|---|---|
| `demand` | req/s que llegan a la entrada (Traefik), incluidas las que esperan |
| `projected` | el tráfico que Aegis espera dentro de T + 20 s |
| `sigma` | cuánto se han equivocado las proyecciones últimamente (req/s) |
| `risk` | probabilidad de pasarse de la capacidad de los pods ya pedidos |
| `ready` | pods Ready ahora |
| `HOLD / SCALE_UP / SCALE_DOWN 1 -> 2` | la decisión y los pods pedidos antes y después |

Las decisiones salen como `WARNING` para que se noten.

**Navegador**: http://localhost:8080 muestra los mismos valores en vivo, con la fórmula del último ciclo y cada escalado ([dashboard.md](dashboard.md)). Si el clúster falla, `cd app && python3 -m aegis.replay --speed 3` reproduce una corrida grabada.

**Terminal 2, pods y HPA**:

```bash
watch -n 2 "kubectl get hpa catalog-service; echo; kubectl get pods -l app=catalog-service"
```

**Terminal 3, el tráfico**: se usa en cada demo de abajo.

## 3. Demo 1: rampa lineal

El tráfico sube de 5 a 50 req/s en 2 minutos, se queda 1 minuto en 50 y baja. Un pod atiende C ≈ 24 req/s (máquina de desarrollo): k6 pasa ese valor en el segundo 81.

En la terminal 3:

```bash
kubectl apply -f kubernetes/load/linear.yaml
kubectl logs -f job/load-linear
```

| Cuándo (s desde que arrancó k6) | Dónde | Qué ves | Qué decir |
|---|---|---|---|
| 0–30 | T1 | `demand` ≈ 5, riesgo 0% | Un pod alcanza |
| 30–60 | T1 | `demand` sube, `projected` va adelante | Aegis extrapola la tendencia T + 20 s hacia adelante |
| ~65–75 | T1 | `SCALE_UP 1 -> 2` con riesgo ≥ 70% | El tráfico todavía está bajo C; la proyección no |
| ~80–90 | T2 | un segundo pod pasa de `0/1` a `1/1` | El pod nuevo está Ready cerca del segundo 81, cuando el tráfico pasa C |
| ~110–150 | T1 | `SCALE_UP 2 -> 3` | Cerca de 50 req/s dos pods (2C ≈ 48) no alcanzan: pide un tercero |
| 240 | T3 | resumen de k6: `http_req_failed` de unos pocos % como mucho (2.5% en promedio en la prueba 1) | Con el HPA solo, la misma rampa falla ~37% (prueba 3) |
| ~285–330 | T1 | `SCALE_DOWN 3 -> 2`, luego `2 -> 1` | Un pod menos a la vez, cada uno tras 60 s de riesgo bajo |

Cuando termine (Ctrl+C en la terminal 3; el Job guarda su pod 10 min, es normal):

```bash
python3 scripts/experiments/reset.py
```

Deja Aegis corriendo en la terminal 1.

## 4. Demo 2: tráfico fluctuante

Dos olas que suben como la rampa, 560 s en total: 30 s en 5 req/s, una ola hasta 30 req/s (necesita 2 pods), 105 s en 5 req/s, una ola hasta 50 req/s (necesita 3 pods, 2C ≈ 48), 120 s en 5 req/s. Tiempos de la prueba 2.

En la terminal 3:

```bash
kubectl apply -f kubernetes/load/fluctuating.yaml
kubectl logs -f job/load-fluctuating
```

| Cuándo (s) | Qué ves | Qué decir |
|---|---|---|
| ~75 | `SCALE_UP 1 -> 2` en la primera subida | Igual que en la demo 1: antes de que la ola pase C (~79 s) |
| 95–140 | tráfico plano en 30, 2 pods | Dos pods alcanzan para esta ola |
| ~215–220 | `SCALE_DOWN 2 -> 1` mientras el tráfico está en 5 | **Aegis devuelve el pod** cuando no hace falta, tras 60 s de riesgo bajo |
| ~305 | `SCALE_UP 1 -> 2` en la segunda subida | Empieza la segunda ola: pide otra vez antes de C |
| ~365 | `SCALE_UP 2 -> 3` | La segunda ola pasa 2C: pide el tercer pod |
| ~500–570 | `SCALE_DOWN 3 -> 2`, luego `2 -> 1` | Vuelve a 1 pod, de a un paso |
| 560 | T3: resumen de k6 | Menos de 1% de fallidas (0.32–0.97% en la prueba 2) |

Cuando termine:

```bash
python3 scripts/experiments/reset.py
```

## 5. El HPA solo (mostrar las gráficas, no en vivo)

En vivo tarda ~15 minutos. Mejor muestra `docs/tests/test3-hpa-baseline/`, o la pestaña *Experimentos* del dashboard con las pruebas 1 y 3 lado a lado.

Para correrlo en vivo de todas formas: detén Aegis (Ctrl+C en la terminal 1) y luego

```bash
kubectl apply -f kubernetes/hpa/baseline.yaml
kubectl apply -f kubernetes/load/linear.yaml
```

y al final `python3 scripts/experiments/reset.py` (vuelve a poner el HPA de Aegis).

## 6. Si algo falla

| Síntoma | Solución |
|---|---|
| `permission denied ... docker.sock` | El usuario todavía no está en el grupo `docker`: `sudo usermod -aG docker $USER`, luego cierra sesión y vuelve a entrar |
| `pip install` dice `externally-managed-environment` | El entorno virtual no está activo: `source .venv/bin/activate` |
| `ModuleNotFoundError: No module named 'kubernetes'` (o `yaml`) | Lo mismo: activa `.venv` en esa terminal |
| `minikube start` falla por memoria | Dale menos: `MINIKUBE_MEMORY=3g scripts/setup.sh`, o cierra otros programas |
| `setup.sh` se detiene por tiempo mientras descarga imágenes | Internet lento: corre `scripts/setup.sh` otra vez, sigue donde quedó |
| Aegis dice `No calibration found` | `cd app && python3 -m aegis.calibrate` |
| `demand=-` y avisos `Prometheus did not answer` | Prometheus se está reiniciando; Aegis sigue y se recupera solo. `python3 scripts/check_env.py` |
| `kubectl apply` dice que el Job es inmutable | Quedó un Job anterior: `python3 scripts/experiments/reset.py` |
| `/api/books` devuelve 500 | `scripts/setup.sh` (vuelve a llenar la tabla) |
| Aegis arranca con más de 1 pod | Detenlo, `python3 scripts/experiments/reset.py`, arráncalo otra vez |
| `Address already in use` (puerto 8080) | Sigue corriendo otro Aegis o un replay: `pkill -f aegis.replay` (o detén el otro Aegis), o arranca con `--port 8081` |
