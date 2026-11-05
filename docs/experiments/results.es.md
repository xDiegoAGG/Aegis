# Resultados del diseño de experimentos

[English](results.md) · Campaña del 2026-11-05: **54 corridas** (3 autoscalers × 3 cargas × 6 bloques), en el orden aleatorio registrado en [design.es.md](design.es.md) antes de la primera corrida. Ninguna corrida se descartó ni se repitió. Datos crudos: `docs/tests/<carga>-<autoscaler>/data/`; análisis generado: [design-results.md](../tests/design-results.md); desviaciones: [design.es.md, sección 10](design.es.md#registro-de-desviaciones).

## 1. En un párrafo

Con las mismas cargas, **Aegis tuvo menos peticiones fallidas que los dos HPA en 5 de los 6 contrastes registrados**: en la rampa, 1.9 % frente a 16.9 % (HPA por defecto) y 15.4 % (HPA afinado); en el pico, 5.6 % frente a 26.7 % y 24.9 %; y en las olas, 1.4 % frente a 7.1 % (HPA afinado). La excepción son las olas frente al HPA por defecto (1.4 % frente a 3.7 %, no significativo): ese HPA conserva sus pods 300 s, lo que le ayuda entre ola y ola y le cuesta un 37 % más de pods-minuto. Aegis estuvo degradado la mitad del tiempo o menos en la rampa y el pico, y pidió el 2º pod 1–2 minutos antes. **H2 se refuta**: la ventaja en el pico, donde no hay tendencia que anticipar, es al menos tan grande como en la rampa. La ganancia no viene solo de anticipar: Aegis reacciona cada 5 s a las peticiones por segundo, y el HPA a la CPU promediada. **H3 también se refuta**: con la regla de bajada de 15–60 s, Aegis usó los mismos o menos pods-minuto que los HPA, salvo en el pico frente al HPA afinado.

## 2. Métrica principal: peticiones fallidas (%)

Media de 6 bloques ± desviación estándar [mín–máx].

| Carga | Aegis | HPA por defecto | HPA afinado |
|---|---|---|---|
| Rampa | **1.9 ± 2.3** [0.0–5.4] | 16.9 ± 9.2 [9.8–34.5] | 15.4 ± 9.6 [4.1–32.6] |
| Pico | **5.6 ± 1.1** [4.5–7.7] | 26.7 ± 15.7 [17.4–58.2] | 24.9 ± 4.6 [21.1–34.0] |
| Olas | **1.4 ± 1.8** [0.0–4.4] | 3.7 ± 3.2 [0.0–8.3] | 7.1 ± 2.6 [3.9–11.7] |

### Contrastes registrados (H1)

ANOVA de bloques aleatorizados por carga; Holm sobre los 6 contrastes. Donde los residuos no son normales (el pico, Shapiro-Wilk p = 0.015) se decide por rangos, como fija el plan.

| Carga | Contraste | Diferencia [IC 95 %] | p Holm | Decidido con | δ de Cliff | **H1** |
|---|---|---|---|---|---|---|
| Rampa | Aegis − HPA por defecto | −15.0 [−25.3, −4.8] | 0.026 | ANOVA | −1.00 | **Se sostiene** |
| Rampa | Aegis − HPA afinado | −13.6 [−23.8, −3.3] | 0.030 | ANOVA | −0.94 | **Se sostiene** |
| Pico | Aegis − HPA por defecto | −21.0 [−31.4, −10.6] | 0.001 | rangos | −1.00 | **Se sostiene** |
| Pico | Aegis − HPA afinado | −19.2 [−29.6, −8.8] | 0.0001 | rangos | −1.00 | **Se sostiene** |
| Olas | Aegis − HPA por defecto | −2.3 [−5.7, +1.2] | 0.18 | ANOVA | −0.39 | No se demostró |
| Olas | Aegis − HPA afinado | −5.6 [−9.1, −2.2] | 0.019 | ANOVA | −0.94 | **Se sostiene** |

δ de Cliff = −1 significa que todas las corridas de Aegis fallaron menos que todas las de ese HPA.

### Sensibilidad (post hoc, no estaba en el plan)

Las corridas de Aegis varían mucho menos que las de los HPA, así que el supuesto de varianzas iguales del ANOVA se cumple mal. Dos análisis que no lo necesitan:

- **t pareado por bloque sobre log(1 + %)**: los mismos 5 contrastes son significativos tras Holm.
- **t pareado por bloque sobre el % sin transformar** (el más conservador, 5 grados de libertad): 2 significativos (rampa frente al HPA por defecto y pico frente al HPA afinado) y 3 en p = 0.063.

La dirección es la misma en todos los análisis. El resumen honesto: **5 de 6 contrastes significativos según el análisis registrado y en escala log; con el análisis más conservador, 2 significativos y 3 al borde.**

## 3. H2: ¿el beneficio necesita una tendencia?

(Aegis − HPA por defecto en la rampa) − (Aegis − HPA por defecto en el pico), pareado por bloque: **+6.0 puntos [−4.3, +16.2], p = 0.20**. No se cumple la regla registrada (intervalo bajo 0); la estimación incluso apunta al lado contrario. **H2 no se sostiene.**

Por qué: en el pico, Aegis pidió el 2º pod a los 45 s (los HPA, a los 103–127 s), 12 s después de que el tráfico superara un pod. Reaccionó, no anticipó, pero reaccionó con la señal que importa (peticiones por segundo, cada 5 s) en lugar de la CPU promediada por metrics-server durante un minuto. La anticipación explica la rampa (el 2º pod está listo 4–9 s después de que el tráfico supera C); la reacción rápida con la señal correcta explica el pico.

## 4. Métricas secundarias (exploratorias, sin corrección)

| Carga | Métrica | Aegis | HPA por defecto | HPA afinado |
|---|---|---|---|---|
| Rampa | Segundos degradado | **58** | 123 | 129 |
| Rampa | Pods-minuto (ventana común) | **15.1** | 18.5 | 15.9 |
| Rampa | Pide el 2º pod a los (s) | **77** | 148 | 138 |
| Pico | Segundos degradado | **46** | 123 | 113 |
| Pico | Pods-minuto | 13.9 | 15.6 | **12.3** |
| Pico | Pide el 2º pod a los (s) | **45** | 127 | 103 |
| Olas | Segundos degradado | 66 | **60** | 113 |
| Olas | Pods-minuto | **21.5** | 29.4 | 22.7 |
| Olas | Pide el 2º pod a los (s) | **75** | 196 | 126 |
| Olas | Idas y vueltas (total en 6 corridas) | 1 | 0 | 5 |

- **Degradación:** Aegis está degradado menos de la mitad del tiempo que cualquiera de los HPA en la rampa y el pico (p < 0.0001). En las olas iguala al HPA por defecto.
- **Costo (H3):** Aegis usa menos pods-minuto que el HPA por defecto en las tres cargas (−8 en las olas). Frente al HPA afinado: sin diferencia en rampa y olas; **en el pico el HPA afinado usa menos** (12.3 frente a 13.9), pero falla 4.4 veces más. Además, Aegis es el más predecible en costo (desviación de 0.2 pods-minuto frente a 0.5–4.3).
- **Idas y vueltas:** el HPA afinado volvió a pedir 5 veces, en sus 6 corridas de olas, un pod que había devuelto menos de 120 s antes; Aegis, una vez.

## 5. Comparado con la campaña de octubre

El HPA por defecto falló un **16.9 %** en la rampa en esta campaña, frente al **37 %** de octubre. No es una comparación de igual a igual, y el número de octubre ya no debería citarse como la tasa de fallos del HPA:

1. **La probe de readiness** ahora corre fuera de la cola de peticiones (`services/catalog-service/src/health.js`) para todos los autoscalers. Un pod saturado ya no deja de estar listo, y eso también ayuda al HPA.
2. **El equipo corrió en modo Rendimiento** y su capacidad derivó hacia arriba durante la campaña (C medida 22 → 30 → 24 req/s, [registro de desviaciones](design.es.md#registro-de-desviaciones)). Con la calibración fija en 22, los pods tenían más margen real del que Aegis suponía.

Lo que se mantiene en ambas campañas es el orden y el tamaño de la brecha: en octubre Aegis bajó los fallos de la rampa del 37 % al 2.5 %; aquí, del 16.9 % al 1.9 %.

## 6. Amenazas a la validez

Las de [design.es.md, sección 8](design.es.md#8-amenazas-a-la-validez), más estas, identificadas después de registrar el plan:

| Amenaza | Efecto | Estado |
|---|---|---|
| **C derivó hasta +36 %** dentro de una sesión | Aegis decidió con C = 22 mientras la capacidad real era mayor: pidió pods antes de lo necesario. Juega en contra de Aegis en costo, no a favor. El término de bloque absorbe la parte entre sesiones | Anotado; C se mantuvo fija como se registró |
| **Varianzas desiguales** | Los p del ANOVA son aproximados | Sensibilidad post hoc (sección 2): misma dirección, 2–5 contrastes significativos según el análisis |
| **Vistazos intermedios** con 2, 3, 4 y 5 bloques | Podrían tentar a parar antes | No se cambió nada y la campaña corrió sus 6 bloques registrados |
| **Generador de carga en el mismo nodo** que el servicio | k6, Traefik y Prometheus compiten con los pods por el nodo | Igual para todos los autoscalers; no se midió |
| **Regla de bajada elegida con trazas de octubre de las mismas cargas** | Su ventaja en costo puede ser optimista con tráfico nuevo | Afecta a los pods-minuto (secundaria), no a los fallos |
| **Los pods-minuto solo son dinero si se cobra por pod** (Fargate, GKE Autopilot) | En nodos fijos, menos pods no ahorran nada si el nodo no se elimina | Declarado para el business case |
| **Un nodo, pods de 60m, 3 réplicas, carga sintética, un solo HPA afinado** | Validez externa | Los resultados valen para este laboratorio; producción necesita su propia evaluación |

## 7. Qué se puede afirmar y qué no

**Se puede afirmar** (en este laboratorio y con estas cargas): Aegis reduce las peticiones fallidas frente al HPA por defecto en rampas y picos, y frente a un HPA afinado de antemano en rampas, picos y olas, con la mitad o menos del tiempo degradado y sin usar más pods, salvo en picos frente al HPA afinado.

**No se puede afirmar:** que el beneficio venga solo de anticipar (H2 refutada); que se mantenga en producción o con decenas de réplicas; que el 37 % de octubre sea hoy la tasa de fallos del HPA.
