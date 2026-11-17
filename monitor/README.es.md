# Monitor de Aegis

[English](README.md)

Monitor web en vivo de Aegis, en React (Vite + Recharts). Lee `GET /api/state` cada 2 s y muestra solo lo que pasa ahora:

- **Tarjetas:** demanda, riesgo, pods Ready/pedidos, P95, C y T, σ y la última decisión.
- **Enviar tráfico:** Rampa, Pico y Olas lanzan una carga real de k6 dentro del clúster (`POST /api/load`); Detener la termina. Una carga a la vez, cada una con tiempo máximo, y solo con la clave.
- **Cuatro gráficas** con el mismo eje, en hora de Colombia (UTC−5) sin importar la zona del computador: peticiones por segundo (demanda, proyección y capacidad de los pods Ready), riesgo (líneas de 70% y 30%, marcas ▲/▼ en cada decisión), pods (pedidos por Aegis, Ready, los que quiere el HPA) y latencia P95 (línea en L). Ventana de 5, 15 o 30 minutos.
- **Decisiones:** las últimas subidas y bajadas con su razón.

## Correrlo en local

Aegis debe estar corriendo (`cd app && python3 -m aegis.actuator`, o en el clúster con `kubectl port-forward -n aegis-system svc/aegis 8080`).

```bash
cd monitor
npm install
npm run dev          # http://localhost:5173, /api va a http://localhost:8080
npm test             # pruebas unitarias (hora de Colombia, series, cliente de cargas)
```

`AEGIS_DEV_API=http://host:puerto npm run dev` apunta el proxy de desarrollo a otro lado.

Los botones necesitan la clave del clúster:

```bash
kubectl get secret aegis-load-key -n aegis-system -o jsonpath='{.data.key}' | base64 -d
```

Un Aegis local la toma de `AEGIS_LOAD_KEY=... python3 -m aegis.actuator`. Sin clave, los botones quedan apagados.

## Construirlo para S3

```bash
VITE_AEGIS_API_URL=http://<host-de-la-api>:8090 npm run build    # archivos estáticos en dist/
```

La API debe permitir el origen del sitio (`AEGIS_ALLOWED_ORIGIN`, lo pone `scripts/setup.sh --monitor-origin`). `scripts/deploy_monitor.sh` lo construye y lo sube.
