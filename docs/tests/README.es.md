# Pruebas

Tres pruebas, una corrida representativa cada una, en minikube (1 nodo, 2 CPUs) el 2026-10-19. Calibración usada por todas (`calibration.json`, medida 17:34–17:49 UTC): **C = 24 req/s por pod** (corridas: 28, 24), **T = 15 s** (14.2, 13.1). Lento significa P95 > L = 1 s durante 15 s.

| Prueba | Tráfico | Modo | Qué muestra |
|---|---|---|---|
| [Prueba 1](test1-linear-ramp/README.es.md) | Rampa 5 → 50 req/s en 2 min | Aegis | Pide el pod antes de que el tráfico pase lo que aguanta uno |
| [Prueba 2](test2-fluctuating/README.es.md) | Dos olas (30 y 50 req/s) | Aegis | Sube en cada ola y baja cuando el tráfico cae |
| [Prueba 3](test3-hpa-baseline/README.es.md) | La misma rampa de la prueba 1 | Solo HPA (CPU 70%) | El HPA normal escala tarde |

## Aegis contra el HPA, la misma rampa

| | Prueba 1 (Aegis) | Prueba 3 (solo HPA) |
|---|---|---|
| El tráfico pasa C | segundo 81 | segundo 81 |
| Pide el 2º pod | segundo 71 (10 s antes) | segundo 142 (61 s después) |
| 2º pod Ready | segundo 84 | segundo 154 |
| Peticiones fallidas | **0.77%** | **30.65%** |
| Segundos con P95 > 1 s | 40 | 140 |
| Máximo de pods | 3 | 2 |
| Pods-minuto | 8.6 | 5.6 |

La prueba 1 se repitió 5 veces: el 2º pod siempre se pidió entre el segundo 70 y el 75, con 0.24–0.95% de fallidas.

## La prueba 2 en corto
Pods 1 → 2 → 1 → 2 → 3 → 2 → 1, **0.22% fallidas**. Con olas el doble de empinadas fallaron 12.59%: Aegis necesita unos T + 20 ≈ 35 s de tendencia visible para adelantarse.

## Correrlas otra vez

```bash
cd scripts/experiments
python3 run.py test1-linear-ramp   # o test2-fluctuating, test3-hpa-baseline
python3 report.py                  # las gráficas otra vez desde los datos guardados
```
