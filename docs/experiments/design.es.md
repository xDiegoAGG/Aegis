# Diseño de los experimentos

[English](design.md) · Plan registrado el 2026-11-04, **antes de correr ninguna corrida**. Lo que dice este documento (factores, métricas, número de corridas, orden y análisis) no se cambia después de ver resultados. Si algo se cambia, se anota en la sección 10 con fecha y motivo.

Complementa a [methodology.md](methodology.md) (preguntas, hipótesis y fases del proyecto). Aquí se responde *cómo* se ponen a prueba esas hipótesis y *por qué así es correcto*.

---

## 1. Resumen

| | |
|---|---|
| **Diseño** | Bloques completos aleatorizados (RCBD), con tratamientos en factorial 3 × 3 |
| **Factor A: autoscaler** | Aegis · HPA por defecto · HPA afinado |
| **Factor B: carga** | Rampa (con tendencia) · Pico (sin tendencia) · Olas (sube y baja dos veces) |
| **Bloques** | 6. Cada bloque corre las 9 combinaciones una vez, en orden aleatorio |
| **Corridas** | 9 × 6 = **54**, unas 13 h (134 min por bloque), repartibles en sesiones de bloques completos |
| **Métrica principal** | % de peticiones fallidas que ve el cliente (k6) |
| **Análisis principal** | ANOVA de dos vías (autoscaler + bloque) por carga; 2 contrastes por carga; Holm sobre 6 contrastes; α = 0.05 |
| **Código** | `scripts/experiments/campaign.py` (orden y ejecución), `design_analysis.py` (análisis), `settings.py` (definición) |

---

## 2. Por qué se reemplazó la campaña de octubre

La campaña del 2026-10-25 (32 corridas) dio una señal clara, pero su diseño tiene fallas que la teoría de diseño de experimentos identifica como amenazas a la validez [1, 2, 9]:

| Falla | Qué pasó | Por qué importa |
|---|---|---|
| **Confusión con el tiempo** | Todo Aegis corrió de 03:24 a 06:14 UTC; todo el HPA, de 14:40 a 16:00 UTC | El autoscaler queda confundido con la hora. Si el laptop estaba más caliente o cargado en la tarde, esa diferencia se suma al efecto de Aegis y no hay forma de separarlas. La aleatorización existe para evitar exactamente esto [1] |
| **Un factor a la vez** | Cada prueba cambiaba una sola cosa | No permite estimar interacciones: si el beneficio de Aegis depende de la carga (H2), hay que medir la interacción autoscaler × carga en un mismo diseño [2, 3] |
| **Grupos sin control** | Olas (prueba 2) y rampas rápidas (6 y 7) solo con Aegis | Sin control no hay comparación: no se puede atribuir nada al autoscaler |
| **n = 3 en varias pruebas** | Pruebas 2, 6, 7 y 8 | Con 3 contra 3, el p exacto más pequeño posible es 0.10: estas pruebas no pueden dar significancia por construcción |
| **Línea base débil** | Solo el HPA por defecto | Comparar contra un rival que se puede mejorar fácilmente es una amenaza a la validez de constructo [9]. "Mejor que el HPA" pasa a significar solo "mejor que el HPA sin afinar" |
| **Costo truncado** | `pod_minutes` dejaba de contar al terminar la carga, y las grabaciones se cortaban con pods activos | Justo la cola, donde sobran pods, quedaba fuera, y de forma distinta para cada autoscaler (el HPA espera 300 s para bajar) |

Los datos de octubre **se conservan** (`docs/tests/test1-…` a `test8-…`) como evidencia preliminar y siguen leyéndose en el dashboard y en los informes, pero las conclusiones formales salen de este diseño.

---

## 3. Unidad experimental, factores y niveles

**Unidad experimental:** una corrida. Desde el reinicio (1 pod listo, sin tráfico, CPU en reposo, HPA recién creado) hasta que termina k6 más una cola de 360 s.

### Factor A: autoscaler (3 niveles)

| Nivel | Configuración | Por qué está |
|---|---|---|
| `aegis` | Aegis escribe `minReplicas` (`kubernetes/hpa/aegis.yaml`), con la regla de bajada de 15–60 s y la probe de readiness en un worker thread | El tratamiento que se evalúa |
| `hpa` | HPA por defecto: CPU 70 %, espera de bajada 300 s (`baseline.yaml`) | Lo que usa casi cualquier clúster sin ajustes: la referencia práctica |
| `hpa-tuned` | HPA afinado: CPU 50 %, espera de bajada 60 s (`tuned.yaml`) | **Control fuerte.** Responde a la objeción "con un HPA bien configurado no hace falta Aegis". Se fijó *antes* de correr y no se ajusta después, para que no se pueda acusar al diseño de haberlo dejado mal a propósito |

Los tres niveles usan la misma imagen del servicio, con la probe nueva, y el mismo máximo de 3 réplicas. La probe es infraestructura, no parte del tratamiento: al aplicarla a todos, la comparación sigue siendo justa.

### Factor B: carga (3 niveles)

| Nivel | Perfil | Qué pone a prueba |
|---|---|---|
| `ramp` | `linear.yaml`: 5 → 50 req/s en 2 min, 1 min arriba | H1: con tendencia, Aegis puede anticipar |
| `spike` | `spike.yaml`: 5 → 45 req/s en 5 s | **H2, control negativo:** sin tendencia, la teoría de Aegis predice poca ventaja. Si Aegis ganara igual en el pico que en la rampa, la explicación sería otra (por ejemplo, simplemente tener más pods) |
| `waves` | `fluctuating.yaml`: dos olas con 2 min bajos entre ellas | H3: la bajada, el costo y las idas y vueltas (quitar un pod y volver a pedirlo) |

Las cargas se escalan por C/24 al correr (`load.py`), así que cruzan la capacidad de un pod en el mismo segundo aunque C cambie entre entornos.

### Factores que se mantienen constantes

Imagen y recursos del pod (60m de CPU), **modo de energía del equipo en "Rendimiento"** (ver el registro de desviaciones del 2026-11-04), un nodo de minikube, máximo de 3 réplicas, C y T de una única calibración, timeout de k6 de 10 s y conexiones sin reutilizar. Mantener fijos los factores que no interesan reduce el ruido sin necesidad de más corridas [2].

---

## 4. Los tres principios de Fisher, y cómo se cumplen

El diseño de experimentos moderno descansa en tres principios [1, 2, 3]. Así los aplica este diseño.

### 4.1 Aleatorización

**Qué dice la teoría.** Si el orden de los tratamientos se sortea, cualquier factor no controlado (calor, procesos de fondo, caché, deriva de C) afecta a todos los tratamientos por igual *en esperanza*. Así los estimadores del efecto quedan insesgados, aunque no sepamos cuáles son esos factores. Además, la aleatorización es lo que justifica la prueba de permutación [1].

**Cómo se cumple.** Dentro de cada bloque, el orden de las 9 combinaciones es una permutación aleatoria distinta:

```python
random.Random(DESIGN_SEED * 1000 + bloque).sample(celdas, 9)   # DESIGN_SEED = 20261104
```

La semilla se fija en este documento y en `settings.py` antes de correr, y el plan completo se guarda en `docs/tests/design-schedule.json`. Cualquiera puede verificar que el orden no se eligió a mano (`python3 campaign.py --plan`).

### 4.2 Repetición

**Qué dice la teoría.** Sin repetir no hay forma de estimar el error experimental, y sin error no hay inferencia. El número de repeticiones se elige por potencia, no por costumbre [2, 4].

**Cómo se cumple.** 6 repeticiones de cada combinación, una por bloque. La sección 6 explica por qué 6.

### 4.3 Bloqueo (control local)

**Qué dice la teoría.** Cuando hay una fuente de variación conocida que no interesa (aquí, la sesión: el día, la hora, el estado del laptop), se agrupan las unidades en bloques homogéneos y se comparan los tratamientos *dentro* de cada bloque. La variación entre bloques sale del error, y la precisión aumenta sin correr más [2, 3].

**Cómo se cumple.** Un bloque es una réplica completa de las 9 combinaciones, unos 134 min seguidos en las mismas condiciones. Las sesiones de trabajo siempre corren bloques completos (`--blocks 1-2`), así que la diferencia entre noches queda en el término de bloque del modelo y no contamina la comparación entre autoscalers. La prueba `test_blocks_absorb_drift` comprueba que un desplazamiento grande entre bloques no cambia la conclusión.

---

## 5. Métricas

Todas se fijan antes de correr.

| Métrica | Tipo | Definición | Por qué |
|---|---|---|---|
| `failed_percent` | **Principal** | Peticiones fallidas o con timeout (> 10 s) ÷ peticiones totales, medido por k6 en el cliente | Es lo que nota el usuario y lo que cuesta dinero. No depende de cómo Kubernetes marque los pods (el artefacto de Ready ya documentado), y es una sola cifra por corrida |
| `degraded_seconds` | Secundaria | Segundos con P95 > 1 s o > 1 % de fallos, durante al menos 15 s seguidos | La definición operativa de degradación de [methodology.md](methodology.md) (H1) |
| `pod_minutes_window` | Secundaria | Pods pedidos × tiempo, desde el inicio de k6 hasta el final de la carga + 360 s | Costo (H3). La ventana es igual para todos y lo bastante larga para que hasta el HPA por defecto (300 s) vuelva a 1 pod |
| `first_scale_up_s` | Secundaria | Segundos desde el inicio de la carga hasta que se pide el 2º pod | El mecanismo: si Aegis anticipa, este número es menor |
| `reasks` | Secundaria | Subidas menos de 120 s después de una bajada | Idas y vueltas (H3, flapping) |

**Una sola métrica principal.** Con varias métricas principales, la probabilidad de encontrar algo "significativo" por azar crece con cada métrica añadida. Fijar una antes de ver los datos evita elegir después la que más conviene [6, 8]. Las secundarias se reportan todas, sin corrección y marcadas como exploratorias.

---

## 6. Tamaño de muestra: por qué 6 bloques

Hay **6 contrastes principales** (2 por carga: Aegis frente a cada HPA) con Holm a α = 0.05. El primer contraste debe pasar 0.05 / 6 = **0.0083** [5].

**Potencia, con la variabilidad medida en octubre** (desviación estándar del % de fallos: rampa 1.5–2.3, pico 1.7–3.7):

| Bloques | Diferencia mínima detectable en la rampa (80 % de potencia) | En el pico |
|---|---|---|
| 5 | 5.3 puntos | 8.0 puntos |
| **6** | **4.6 puntos** | **6.9 puntos** |
| 8 | 3.8 puntos | 5.7 puntos |

Cálculo: error estándar del contraste = σ·√(2/b), con (3−1)(b−1) grados de libertad en el error; diferencia detectable ≈ (t₁₋α/₂ + t₀.₈)·error estándar. En octubre la diferencia frente al HPA por defecto fue de 35 puntos (rampa) y 42 (pico), así que 6 bloques sobran para H1 frente al HPA por defecto. **La diferencia frente al HPA afinado no se conoce**: con 6 bloques se detecta si es de 5–7 puntos o más; si es menor, el resultado será "no se demostró diferencia", y se reporta así.

**Por qué no 5:** con 5 bloques el margen es más estrecho y la corrida cuesta lo mismo por bloque. **Por qué no 8:** son 4.5 h más de clúster para ganar 1 punto de sensibilidad. 6 es el punto razonable.

---

## 7. Plan de análisis

Implementado en `scripts/experiments/design_analysis.py` y probado con datos sintéticos cuyo resultado se conoce de antemano (`DesignTest` en `test_tooling.py`).

### 7.1 Modelo

Para cada carga, el modelo estándar de bloques aleatorizados [2]:

$$y_{ij} = \mu + \tau_i + \beta_j + \varepsilon_{ij}, \qquad i \in \{\text{aegis}, \text{hpa}, \text{hpa-tuned}\},\ j = 1..6$$

τ es el efecto del autoscaler, β el del bloque y ε el error. Se estima con ANOVA de dos vías sin interacción (con una observación por celda, la interacción bloque × tratamiento *es* el error).

### 7.2 Contrastes principales (H1)

Por carga, **Aegis − HPA** y **Aegis − HPA afinado**:

$$t = \frac{\bar y_{\text{aegis}} - \bar y_{\text{hpa}}}{\sqrt{2\,\text{MSE}/b}}, \qquad gl = (3-1)(b-1) = 10$$

con intervalo de confianza del 95 % para la diferencia. Los 6 p se corrigen con **Holm** [5], que controla la probabilidad de cualquier falso positivo (FWER) y es uniformemente más potente que Bonferroni.

**Regla de decisión, fijada de antemano.** H1 se sostiene en una carga si el contraste Aegis − HPA tiene p de Holm < 0.05, diferencia negativa, *y* la versión por rangos (7.4) apunta en la misma dirección. Frente al HPA afinado se aplica la misma regla, por separado.

### 7.3 Interacción (H2)

Si el beneficio de Aegis depende de que haya tendencia, la ventaja sobre el HPA debe ser mayor en la rampa que en el pico. Por bloque:

$$g_j = (y^{\text{rampa}}_{\text{aegis},j} - y^{\text{rampa}}_{\text{hpa},j}) - (y^{\text{pico}}_{\text{aegis},j} - y^{\text{pico}}_{\text{hpa},j})$$

y una prueba t de una muestra sobre los g_j (gl = b − 1). **H2 se sostiene** si el intervalo del 95 % de la media de g queda por debajo de 0. Emparejar por bloque elimina la deriva entre sesiones de esta comparación.

### 7.4 Robustez

Se reporta junto a cada contraste. No cambia la regla de decisión, salvo el respaldo de 7.5.

| Prueba | Para qué |
|---|---|
| **ANOVA sobre rangos** (rank transform, Conover e Iman [7]) | No supone normalidad. El % de fallos está acotado en 0 y puede ser asimétrico |
| **Prueba de aleatorización dentro de bloque** | Es *la* prueba que justifica el propio diseño [1]: intercambiar las etiquetas dentro de cada bloque (2⁶ = 64 arreglos). Su p mínimo es 2/64 = 0.031, así que no puede pasar Holm; por eso confirma la dirección pero no es la prueba principal |
| **Delta de Cliff** [10] | Tamaño de efecto sin supuestos: −1 significa que todas las corridas de Aegis fallaron menos que todas las del HPA |

### 7.5 Diagnóstico y respaldo

- **Shapiro-Wilk sobre los residuos.** Si p < 0.05 (no normales), la decisión de 7.2 se toma con la columna por rangos, también corregida por Holm. Esta regla se fija ahora para no elegir el análisis después de ver los datos.
- **Media de cada bloque.** Una tendencia en una dirección indica deriva entre sesiones; la absorbe el término de bloque, pero se reporta.
- **Deriva de C.** Al final de cada sesión se mide C otra vez sin guardarla (`python3 -m aegis.calibrate --check-only --output docs/tests/calibration-check-<fecha>.json`). Si C cae más de 10 % respecto a la calibración de la campaña, se anota en la sección 10 y se discute en las amenazas a la validez.

### 7.6 Secundarias (exploratorias)

El mismo modelo y los mismos contrastes para `degraded_seconds`, `pod_minutes_window`, `first_scale_up_s` y `reasks`, con intervalos del 95 % y **sin** corrección: describen y generan hipótesis, no confirman. **H3** (Aegis gasta más pods) se responde con el intervalo de `pod_minutes_window`, que se reporta sea cual sea el resultado.

---

## 8. Amenazas a la validez

Clasificación de Wohlin et al. [9] y Shadish, Cook y Campbell [11].

| Tipo | Amenaza | Qué hace el diseño | Qué queda |
|---|---|---|---|
| Interna | Confusión con el tiempo o la sesión | Aleatorización dentro de bloque + bloqueo | — |
| Interna | Arrastre entre corridas (pods, recomendaciones guardadas por el HPA) | `reset()` borra el HPA, deja 1 pod listo, espera tráfico ≈ 0 y CPU < 30 % antes de cada corrida | Cachés de nodo; minimizado por el orden aleatorio |
| Interna | Deriva de C | Una sola calibración + control al final de cada sesión | Se reporta si pasa del 10 % |
| Constructo | Línea base débil | HPA afinado fijado de antemano | Otros afinados posibles (métrica de peticiones, KEDA): fuera de alcance, se declara |
| Constructo | "Ready" no refleja la capacidad real | Métrica principal en el cliente (k6), no en Kubernetes | — |
| Conclusión | Muchas comparaciones | Una métrica principal, Holm, secundarias marcadas | — |
| Conclusión | Supuestos del ANOVA | Diagnóstico + respaldo por rangos fijado de antemano | — |
| Conclusión | Pocas repeticiones | Potencia calculada (sección 6) | Diferencias < 5–7 puntos frente al HPA afinado pueden no detectarse |
| Externa | Un nodo, pods pequeños, carga sintética | Se declara; las cargas cubren tendencia, sin tendencia y oscilación | No generaliza sin más a producción ni a decenas de réplicas |
| Externa | Quien diseña también evalúa | Plan registrado antes de correr, semilla fija, análisis automático | — |

---

## 9. Qué no va al clúster, y por qué

| Pregunta | Dónde se responde | Por qué ahí |
|---|---|---|
| Umbrales (70 % / 30 %), espera de bajada, horizonte | Simulador (`scale_down_sim.py`), con un diseño factorial sobre trazas grabadas y sintéticas | Explorar parámetros en el clúster costaría cientos de corridas. La práctica estándar es explorar barato y confirmar caro [3]: al clúster va solo la configuración elegida |
| Límite de velocidad de rampa (antes pruebas 6 y 7) | Simulador + calibración | Era un barrido de una sola variable sin control y con n = 3; el simulador recorre muchas velocidades con el mismo modelo de riesgo |
| Modo métrica (antes prueba 8) | Prueba funcional de 1 corrida (`run.py test8-metric-mode`) | Es otra forma de conectar Aegis con el HPA, no una hipótesis; no entra en la comparación |
| Horizonte T (H4) | Calibración (`aegis.calibrate`) y `forecast_accuracy.py` | Es una medición del entorno, no un efecto de tratamiento |

---

## 10. Protocolo

0. **Modo de energía en "Rendimiento" y el equipo enchufado** (`sudo tuned-adm profile throughput-performance`). El preflight lo comprueba y cada corrida lo registra (`power_profile`).
1. **Preparar:** `scripts/setup.sh --pod-cpu 60m --build` con la imagen que tiene la probe nueva; comprobar que `kubectl get deploy catalog-service -o yaml` muestra la readiness en `/ready:3004`.
2. **Calibrar una vez:** `python3 -m aegis.calibrate`. C y T quedan fijos para toda la campaña (`run.py` impide mezclar calibraciones dentro de una prueba).
3. **Ver el plan:** `python3 scripts/experiments/campaign.py --plan`.
4. **Correr por sesiones de bloques completos:** `python3 scripts/experiments/campaign.py --blocks 1-2`, después `--blocks 3-4` y `--blocks 5-6`. El preflight se ejecuta antes de cada sesión, y si algo falla la sesión se retoma con el mismo comando.
5. **Control de deriva al final de cada sesión:** `python3 -m aegis.calibrate --check-only --output docs/tests/calibration-check-<fecha>.json`.
6. **Analizar:** `campaign.py` lo hace solo al terminar; a mano, `python3 scripts/experiments/design_analysis.py` → `docs/tests/design-results.md`.
7. **No tocar nada a mitad de la campaña:** ni la imagen, ni `config.yaml`, ni los manifiestos. Si es inevitable, se anota abajo y se repiten los bloques afectados.

### Registro de desviaciones

| Fecha | Desviación | Motivo | Bloques afectados |
|---|---|---|---|
| 2026-11-04 | Se agregó el modo de energía a los factores constantes y al preflight, **antes de la primera corrida** | La primera calibración dio C = 4 req/s (octubre: 22) con el equipo en "balanced". Con un pod de 60m, la CPU trabaja a ráfagas cortas y el procesador no sube de frecuencia: el mismo cálculo fijo costó 21 ms de CPU dentro del pod frente a 6.5 ms en "Rendimiento". Se descartaron la imagen nueva (una prueba A/B con la imagen anterior dio lo mismo), las dependencias (iguales al lock) y el JIT (igual tras 600 peticiones) | Ninguno: aún no había corridas |
| 2026-11-05 | Control de deriva al cerrar la sesión de los bloques 1–3: **C medida = 30 req/s** (dos corridas: 30, 30) frente a C = 22 de la calibración de la campaña (+36 %, sobre el umbral del 10 %). T = 11 s (calibrado: 12 s). `docs/tests/calibration-check-2026-11-05.json` | El rendimiento del equipo cambió a lo largo de la sesión; coincide con que el bloque 1 tuvo más fallos que el 2 y el 3 en las tres cargas. **Se mantiene C = 22 para los bloques 4–6**, como fija el plan (una sola calibración): recalibrar cambiaría el tratamiento de Aegis entre bloques. El término de bloque absorbe la diferencia entre sesiones; dentro de cada bloque los tres autoscalers comparten condiciones. Con C real mayor que la usada, Aegis fue más conservador (más pods), lo que perjudica a Aegis en costo, no lo favorece. Se repite el control al final de cada sesión | Todos; se discute en las amenazas a la validez |
| 2026-11-05 | Control de deriva al cerrar la sesión de los bloques 4–6: **C medida = 24 req/s** (24, 24), +9 % sobre C = 22, dentro del umbral. T = 12 s. `docs/tests/calibration-check-2026-11-05-end.json`. Además, el primer intento de lanzar los bloques 5–6 se detuvo en el preflight por un falso positivo de "No other Aegis" (detectó la línea de comando del propio script de sesión); se relanzó sin cambios, sin corridas perdidas | C fluctuó 22 → 30 → 24 durante la campaña; el término de bloque lo absorbe. Ninguna corrida se descartó ni se repitió | Ninguno |

---

## Referencias

[1] R. A. Fisher, *The Design of Experiments*. Oliver and Boyd, 1935.
[2] D. C. Montgomery, *Design and Analysis of Experiments*, 9th ed. Wiley, 2017. (Cap. 4: bloques completos aleatorizados).
[3] G. E. P. Box, J. S. Hunter y W. G. Hunter, *Statistics for Experimenters*, 2nd ed. Wiley, 2005.
[4] J. Cohen, *Statistical Power Analysis for the Behavioral Sciences*, 2nd ed. Lawrence Erlbaum, 1988.
[5] S. Holm, "A Simple Sequentially Rejective Multiple Test Procedure," *Scandinavian Journal of Statistics*, vol. 6, no. 2, pp. 65–70, 1979.
[6] B. A. Nosek, C. R. Ebersole, A. C. DeHaven y D. T. Mellor, "The Preregistration Revolution," *PNAS*, vol. 115, no. 11, pp. 2600–2606, 2018.
[7] W. J. Conover y R. L. Iman, "Rank Transformations as a Bridge Between Parametric and Nonparametric Statistics," *The American Statistician*, vol. 35, no. 3, pp. 124–129, 1981.
[8] R. Jain, *The Art of Computer Systems Performance Analysis*. Wiley, 1991. (Parte IV: diseño de experimentos para sistemas).
[9] C. Wohlin, P. Runeson, M. Höst, M. C. Ohlsson, B. Regnell y A. Wesslén, *Experimentation in Software Engineering*. Springer, 2012.
[10] N. Cliff, "Dominance Statistics: Ordinal Analyses to Answer Ordinal Questions," *Psychological Bulletin*, vol. 114, no. 3, pp. 494–509, 1993.
[11] W. R. Shadish, T. D. Cook y D. T. Campbell, *Experimental and Quasi-Experimental Designs for Generalized Causal Inference*. Houghton Mifflin, 2002.
