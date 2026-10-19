# Demo en vivo

Dos demos en consola, de unos 6 y 10 minutos:

1. **Rampa lineal**: Aegis pide un pod **antes** de que el tráfico pase lo que un pod puede atender.
2. **Tráfico fluctuante**: Aegis sube en cada ola y **baja** cuando el tráfico cae.

Los números de abajo salen de las 5 corridas de cada prueba (`docs/tests/`). Cambian un poco de una corrida a otra.

## 1. Una máquina nueva, desde cero (unos 45 minutos, hazlo antes de la clase)

Probado en Linux (Kali, basado en Debian) con las versiones de abajo; los comandos son para Ubuntu o Debian en un PC de 64 bits Intel/AMD.

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

Crea el clúster de minikube y descarga todas las imágenes (Prometheus, Traefik, DynamoDB Local, k6, Node.js). Tiene que terminar con `Environment ready`. La última línea dice `Aegis calibration - not calibrated yet`: es lo esperado en una máquina nueva. Si el PC tiene más recursos, dale más a minikube: `MINIKUBE_CPUS=4 MINIKUBE_MEMORY=6g scripts/setup.sh` (solo la primera vez, cuando se crea el clúster).

### 1.4 Calibrar (~17 min, una vez por máquina)

C y T dependen de la máquina, así que se miden en esta. No puede correr nada más mientras tanto.

```bash
cd app
python3 -m aegis.calibrate
cd ..
```

Termina con `Saved in ConfigMap aegis-calibration: C=… req/s, T=… s`. Los perfiles de tráfico se hicieron para un C entre 20 y 30 req/s (en la máquina de desarrollo C = 24): con un C en ese rango, la demo 1 necesita 2–3 pods y la demo 2 va 1 → 2 → 1 → 3 → 1.

### 1.5 Dejarlo en reposo

```bash
python3 scripts/check_env.py           # todas las líneas OK, y la calibración
python3 scripts/experiments/reset.py   # 1 pod, sin tráfico
```

Si después se apaga el PC, `scripts/setup.sh` recupera todo en pocos minutos y la calibración se conserva.

## 2. Terminales

Abre tres terminales en la raíz del repositorio y en cada una corre `source .venv/bin/activate`. No hace falta ningún túnel: Aegis llega a Prometheus a través de la API de Kubernetes.

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

Las líneas con una decisión salen como `WARNING` para que se noten. No es un error.

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
| 240 | T3 | resumen de k6: `http_req_failed` cerca de 1% o menos | Casi nadie notó la rampa |
| ~285–330 | T1 | `SCALE_DOWN 3 -> 2`, luego `2 -> 1` | Un pod menos a la vez, cada uno tras 60 s de riesgo bajo |

Cuando termine (Ctrl+C en la terminal 3 para dejar de seguir el log; el Job guarda su pod 10 min para que los experimentos copien los resultados, es normal):

```bash
python3 scripts/experiments/reset.py
```

Deja Aegis corriendo en la terminal 1.

## 4. Demo 2: tráfico fluctuante

Dos olas: hasta 40 req/s (necesita 2 pods), 2 minutos en 8 req/s, hasta 55 req/s (necesita 3 pods, 2C ≈ 48), 2 minutos en 8 req/s.

En la terminal 3:

```bash
kubectl apply -f kubernetes/load/fluctuating.yaml
kubectl logs -f job/load-fluctuating
```

| Cuándo (s) | Qué ves | Qué decir |
|---|---|---|
| 30–90 | `SCALE_UP 1 -> 2` en la primera subida, quizás `2 -> 3` al final | Igual que en la demo 1 |
| 90–135 | tráfico plano en 40 | Si pidió un 3er pod, ahora el riesgo con uno menos es bajo |
| 150–230 | `SCALE_DOWN` hasta 1 pod mientras el tráfico está en 8 | **Aegis devuelve los pods** cuando no hacen falta, tras 60 s de riesgo bajo |
| 255–300 | `SCALE_UP` otra vez, hasta 3 pods | La segunda ola es más alta que 2C: pide el tercer pod |
| 345–480 | `SCALE_DOWN 3 -> 2`, luego `2 -> 1` | Vuelve a 1 pod, de a un paso |
| 480 | resumen de k6 | Pocas o ninguna petición fallida |

Cuando termine:

```bash
python3 scripts/experiments/reset.py
```

## 5. El HPA solo (mostrar las gráficas, no en vivo)

Correr el HPA normal en vivo tarda unos 10 minutos y su bajada otros 5. Mejor muestra `docs/tests/test3-hpa-baseline/`: la misma rampa de la demo 1, donde el HPA pide el segundo pod recién cuando la CPU ya está alta, después de que se rompió la latencia.

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
| `ModuleNotFoundError: No module named 'scipy'` (o `kubernetes`, `yaml`) | Lo mismo: activa `.venv` en esa terminal |
| `minikube start` falla por memoria | Dale menos: `MINIKUBE_MEMORY=3g scripts/setup.sh`, o cierra otros programas |
| `setup.sh` se detiene por tiempo mientras descarga imágenes | Internet lento: corre `scripts/setup.sh` otra vez, sigue donde quedó |
| Aegis dice `No calibration found` | `cd app && python3 -m aegis.calibrate` |
| `demand=-` y avisos `Prometheus did not answer` | Prometheus se está reiniciando; Aegis sigue y se recupera solo. `python3 scripts/check_env.py` |
| `kubectl apply` dice que el Job es inmutable | Quedó un Job anterior: `python3 scripts/experiments/reset.py` |
| `/api/books` devuelve 500 | `scripts/setup.sh` (vuelve a llenar la tabla) |
| Aegis arranca con más de 1 pod | Detenlo, `python3 scripts/experiments/reset.py`, arráncalo otra vez |

Para ver las mismas demos como gráficas, cada corrida de las pruebas está en `docs/tests/` (`run-N.png` y `all-runs.png`).
