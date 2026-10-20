# Prueba 1: Aegis con una rampa lineal

**Fecha:** 2026-10-19, 17:54:37 – 18:00:00 UTC
**Objetivo:** mostrar que Aegis predice el tráfico y pide un pod antes de que un solo pod deje de alcanzar.

## Qué se hizo
- Tráfico (`kubernetes/load/linear.yaml`): 30 s a 5 req/s, 2 min de 5 a 50 req/s, 1 min en 50, 30 s bajando.
- Aegis corriendo (`python3 -m aegis.actuator`) con el HPA de `kubernetes/hpa/aegis.yaml`.
- Calibración de esta máquina: C = 24 req/s por pod, T = 15 s. El tráfico pasa C en el segundo 81 y 2C (48) en el segundo 145.
- Latencia medida por k6, del lado del cliente.

## Resultados

![Prueba 1](chart.png)

| Segundo (desde que arrancó k6) | Qué pasó |
|---|---|
| 71 | Aegis pide el 2º pod: demanda 15.7 req/s, proyección 27.3, riesgo 73.9% |
| 81 | El tráfico pasa lo que un pod puede atender (C = 24) |
| 84 | El 2º pod está Ready |
| 131 | Aegis pide el 3er pod (proyección 51.8 > 2C) |
| 240 | Termina la carga |
| 286 | Aegis vuelve a 2 pods, 60 s después de que bajó el riesgo |

k6: 7266 peticiones, **0.77% fallidas**, P95 1.38 s. 40 s con el P95 sobre 1 s, mientras arrancaba el 3er pod (el nodo tiene solo 2 CPUs y un pod que arranca le quita CPU a los otros).

## Conclusión
Aegis pidió el 2º pod **10 s antes** de que el tráfico pasara lo que aguanta un pod, así que estaba atendiendo justo cuando hizo falta. Con el HPA normal, la misma rampa tuvo 30.65% de peticiones fallidas ([prueba 3](../test3-hpa-baseline/)).

## No fue suerte
La misma prueba se repitió 4 veces más (`data/repeat-runs-summary.json`):

| Corrida | 2º pod pedido (s) | 2º pod Ready (s) | Fallidas | Pods |
|---|---|---|---|---|
| 1 (gráfica) | 71 | 84 | 0.77% | 1 → 2 → 3 → 2 |
| 2 | 71 | 84 | 0.95% | 1 → 2 → 3 → 2 |
| 3 | 71 | 84 | 0.48% | 1 → 2 → 3 → 2 |
| 4 | 75 | 87 | 0.84% | 1 → 2 → 3 → 2 |
| 5 | 70 | 82 | 0.24% | 1 → 2 → 3 → 2 |

Datos: `data/run-1.csv` (cada 5 s), `data/run-1-aegis.ndjson` (cada ciclo de Aegis), `data/run-1-k6.log`, `data/run-1-summary.json`.
