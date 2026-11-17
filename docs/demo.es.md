# Demo en vivo

[English](demo.md)

Aegis corre en EKS y el monitor es un sitio web en S3. Todo se muestra en el navegador: un botón manda tráfico real (k6 dentro del clúster), y las cuatro gráficas muestran a Aegis pidiendo pods **antes** de que falten y devolviéndolos después. Tres demos: Rampa (~4 min), Olas (~9 min) y Pico (~3 min). Si AWS falla, la misma demo corre en minikube (sección 7).

## 1. Antes de la clase (~45 min)

Seguir [aws.es.md](aws.es.md): credenciales, `scripts/eks_up.sh`, `scripts/push_images.sh`, `scripts/setup.sh --aegis --registry …`, calibración y `scripts/deploy_monitor.sh`. Después revisar:

```bash
python3 scripts/check_env.py      # todo OK, con C y T
python3 scripts/reset.py          # sin carga, 1 pod
kubectl get secret aegis-load-key -n aegis-system -o jsonpath='{.data.key}' | base64 -d    # la clave de carga
```

`deploy_monitor.sh` imprime la URL del monitor. Abrirla, pegar la clave en **Load key** y comprobar que arriba diga **Live**. Si Aegis se reinicia, las gráficas quedan vacías; es normal.

## 2. Qué hay en la pantalla

| Parte | Qué decir |
|---|---|
| Tarjetas | Demanda ahora, riesgo, pods Ready / pedidos, P95, C y T (medidos por la calibración), σ (aprendido en vivo), última decisión |
| Requests per second | Azul: demanda. Violeta: lo que Aegis espera en T + 20 s. Gris en escalones: lo que aguantan los pods Ready (C × pods) |
| Risk | Probabilidad de quedarse corto **con los pods que Aegis ya pidió**. Al 70% pide uno más; luego el riesgo cae a ~0 porque la fórmula ya cuenta ese pod |
| Pods | Azul: lo que pide Aegis (minReplicas del HPA). Negro: Ready. Naranja punteado: lo que querría el HPA solo, por CPU |
| Latency P95 | El 95% de las peticiones tarda menos que esto; por encima de L = 1 s el servicio cuenta como lento. Se mide sobre 30 s, así que muestra los problemas unos segundos tarde |

Las horas son de Colombia (UTC−5), las mismas del reloj del salón.

## 3. Demo 1: Rampa

Apretar **Ramp**. El tráfico sube de 0,2 C a 2,1 C en 2 minutos, se queda 1 minuto y baja (en EKS con C = 16: de 3 a 34 req/s).

| Cuándo (s después del botón) | Qué se ve | Qué decir |
|---|---|---|
| 0–30 | demanda baja, riesgo 0% | Un pod alcanza |
| 30–70 | la línea violeta sube por delante de la azul | Aegis extrapola la tendencia T + 20 s hacia adelante |
| ~70 | el riesgo pasa el 70%, marca ▲2, el azul sube a 2 | Pide el 2º pod cuando el tráfico todavía está **por debajo** de lo que aguanta un pod |
| ~90 | el negro sube a 2, la capacidad gris se duplica | El pod queda Ready unos T = 17 s después, justo cuando hace falta |
| ~130 | ▲3 | Cerca de 2 C dos pods no alcanzan: pide el tercero |
| ~250–300 | la demanda baja, ▼1 | Aegis devuelve los pods después de 15–60 s de riesgo bajo |

Ensayo en EKS (2026-11-17): 2º pod pedido a los 71 s con 10 req/s, 3º a los 131 s, y de vuelta a 1 pod al terminar la carga.

## 4. Demo 2: Olas

Esperar a que haya 1 pod (la tarjeta de pods dice 1 / 1) y apretar **Waves**: una ola a 1,25 C (necesita 2 pods), 105 s bajo, una ola a 2,1 C (necesita 3 pods), 120 s bajo. Unos 9 minutos.

Qué decir: Aegis sube en cada subida y **vuelve a bajar** entre las olas, así que no se queda con pods que no necesita.

## 5. Demo 3: Pico

Apretar **Spike**: de 0,2 C a 1,9 C en 5 s. Nada lo anuncia, así que Aegis no puede adelantarse: reacciona en los siguientes ciclos, igual antes que el HPA (su línea naranja). Es el límite honesto de proyectar la tendencia.

## 6. Si algo sale mal

| Síntoma | Solución |
|---|---|
| Arriba dice **Aegis unreachable** | `kubectl get pods -n aegis-system`; `kubectl logs -n aegis-system deploy/aegis` |
| Botones apagados, "no load key" | Correr otra vez `scripts/setup.sh --aegis --registry …` (crea el Secret) |
| "Wrong key" | Pegar otra vez la clave (sección 1) |
| "Another load is still running" | Apretar **Stop**, o `python3 scripts/reset.py` |
| Aegis arranca con más de 1 pod | `python3 scripts/reset.py`, y `kubectl rollout restart -n aegis-system deploy/aegis` |
| El navegador bloquea la API (CORS) | `scripts/deploy_monitor.sh` otra vez: permite la URL del sitio |
| `/api/books` devuelve 500 | `scripts/setup.sh --aegis --registry …` (vuelve a llenar la tabla) |
| Vencieron las credenciales de AWS | Copiar las nuevas (aws.es.md) y `aws eks update-kubeconfig --name aegis --region us-east-1` |

## 7. Plan B: minikube en este PC

El mismo monitor y los mismos botones, sin AWS. Necesita una máquina con al menos 4 hilos de CPU y 8 GB de RAM.

```bash
git clone https://github.com/xDiegoAGG/Aegis.git && cd Aegis
python3 -m venv .venv && source .venv/bin/activate
pip install -r app/requirements.txt
scripts/setup.sh --aegis                         # minikube, Prometheus, Traefik, DynamoDB, servicio, HPA, Aegis (~15 min)
cd app && python3 -m aegis.calibrate && cd ..    # C y T, ~17 min, una vez por máquina
scripts/setup.sh --aegis                         # ahora Aegis arranca con la calibración
kubectl port-forward -n aegis-system svc/aegis 8080 &
cd monitor && npm install && npm run dev         # http://localhost:5173
```

Herramientas: Docker, minikube v1.39.0, kubectl, Helm v3, Python 3.11+, Node.js 20+. Si C queda fuera de 20–30 req/s, cambiar el CPU del pod (`scripts/setup.sh --aegis --pod-cpu 60m`, CPU nuevo ≈ CPU probado × C buscado ÷ C medido) y calibrar otra vez. Más memoria para minikube: `MINIKUBE_CPUS=4 MINIKUBE_MEMORY=6g scripts/setup.sh --aegis`.

## 8. Después de la clase

```bash
scripts/eks_down.sh       # borra el clúster y su balanceador
```
