# Las fórmulas de Aegis: de dónde salen y por qué sirven

Cada 5 segundos Aegis responde una sola pregunta:

> Si no hago nada, ¿el tráfico de **dentro de T segundos** va a ser más de lo que mis pods pueden atender?

T es el tiempo que necesita un pod nuevo para estar Ready. Preguntar por "ahora" es tarde: un pod pedido ahora solo ayuda T segundos después. La respuesta sale de cuatro fórmulas, cada una tomada de un campo conocido:

| # | Fórmula | Viene de | Qué le da a Aegis |
|---|---|---|---|
| 1 | capacidad = C · N | Teoría de colas | Dónde se rompe el servicio |
| 2 | r = terminadas + d(esperando)/dt | Conservación del flujo (ley de Little) | El tráfico que **llega**, no solo el que se atiende |
| 3 | p = r + m · (T + retraso) | Pronóstico con tendencia lineal (mínimos cuadrados) | El tráfico de dentro de T segundos |
| 4 | riesgo = Φ((p − C·N) / σ) | Distribución normal de los errores de pronóstico | Qué tan probable es pasarse de la capacidad |
| 5 | σ = √(2 · promedio(max(0, e)²)) | Errores del pronóstico, semidesviación superior | Cuánto confiar en la proyección |

La regla de decisión encima de ellas (70% para subir, 30% durante 60 s para bajar) es histéresis, la misma idea que usa el HPA.

## 1. Capacidad: C · N

**De dónde sale.** Teoría de colas [13][14]. Un servidor que puede terminar μ peticiones por segundo y recibe λ peticiones por segundo está ocupado una fracción ρ = λ/μ del tiempo. En el modelo básico (M/M/1) el tiempo medio de respuesta es

$$W = \frac{1}{\mu - \lambda} = \frac{1/\mu}{1 - \rho}$$

Mientras ρ es chico, W casi no se mueve. Cuando λ se acerca a μ, el denominador va a 0 y W explota. La latencia no es una pendiente, es un **acantilado**.

**Por qué sirve aquí.** Es justo lo que hace el servicio: P95 de ~0.1–0.3 s hasta cierta carga, y segundos justo después. Por eso mirar la latencia es mirar el borde del acantilado demasiado de cerca: cuando sube, ya es tarde. La pregunta útil es "¿λ va a pasar a μ?". C es μ de un pod, en peticiones por segundo.

- **C se mide, no se calcula**: μ depende del límite de CPU, del código, de la base de datos y de la máquina. `python3 -m aegis.calibrate` le pone a un pod una carga en escalones (+2 req/s cada 30 s) y C es el último escalón antes de que el pod se degrade (P95 > L, errores, o deja de dar abasto). Es la prueba de carga de siempre para "encontrar el codo", hecha sola.
- **× N**: Traefik manda cada petición al siguiente pod (round robin), así que con N pods cada uno recibe λ/N. Los pods son iguales, así que la capacidad se suma.

## 2. Demanda: lo que llega, no lo que se atiende

$$r = \text{terminadas por segundo} + \frac{d(\text{peticiones esperando})}{dt}$$

**De dónde sale.** Conservación del flujo, la base de la ley de Little [15]: lo que entra, o sale o se queda adentro. Entonces llegadas = salidas + crecimiento de la cola.

**Por qué sirve aquí.** Un pod no puede terminar más de μ peticiones por segundo. Si Aegis contara solo las terminadas, el número se frenaría cerca de C justo cuando el pod está sobrecargado, y la regla "escala cuando la demanda pase de C" nunca se activaría. Eso pasó durante el desarrollo: k6 mandaba 50 req/s y el contador del propio pod mostraba 29.6. Traefik, en la entrada, da los dos términos: las peticiones terminadas por segundo, y las conexiones abiertas (una por petición en curso), cuya derivada es el crecimiento de la cola.

## 3. Proyección: p = r + m · (T + retraso)

**De dónde sale.** Extrapolación de una tendencia lineal, el método de pronóstico con tendencia más simple [16]. Es la aproximación de Taylor de primer orden r(t + h) ≈ r(t) + r′(t) · h. La pendiente m se estima con mínimos cuadrados ordinarios sobre los últimos 30 s (6 muestras), la forma estándar de ajustar una tendencia lineal y suavizar el ruido. El método de tendencia lineal de Holt (nivel + tendencia × horizonte) es la misma idea [16], y los autoescaladores predictivos usan esta familia de modelos [4][5][17][18].

**Por qué el horizonte es T + retraso.**
- **T** es el tiempo de aprovisionamiento, medido por la calibración (desde que se piden pods hasta que están Ready). Mirar menos de T hacia adelante es reaccionar tarde; mirar mucho más pide pods demasiado pronto.
- **retraso**: la demanda sale de una tasa sobre una ventana de 30 s, que describe el centro de la ventana más una lectura de Prometheus. Medido sobre una rampa real, iba 19 s detrás del tráfico que mandaba k6; Aegis usa 20 s. Sin él, la proyección apuntaría a "dentro de T − 20 segundos".

**Por qué algo tan simple.** El horizonte es corto (~40 s), corre cada 5 s, no hay datos para entrenar, y cada decisión tiene que poder explicarse. En horizontes tan cortos una tendencia lineal es una referencia fuerte. Su debilidad conocida: cuando una rampa se detiene, sigue proyectando la subida un momento y puede pedir un pod de más. Aegis lo quita después (regla 6), y las pruebas miden ese costo en pod-minutos.

**Comparado con otros pronósticos** ([forecast.md](tests/forecast.md)). Sobre las 22 corridas de Aegis, Holt amortiguado [21] tiene el menor error a 35 s (MAE 7.2 contra 8.1 req/s; ingenuo 10.9) porque se pasa menos cuando una rampa se detiene. Pero con el motor de decisión completo, la tendencia lineal deja menos segundos bajo capacidad (21.6 por corrida contra 22.8 Holt amortiguado, 26.8 lineal amortiguada, 106.9 ingenuo) con los mismos pods-minuto. Pasarse cuesta un pod durante un minuto; quedarse corto cuesta peticiones fallidas. Se mantuvo la tendencia lineal; un pronóstico para ese costo asimétrico queda como trabajo futuro.

## 4. Riesgo: Φ((p − C·N) / σ)

**De dónde sale.** La proyección nunca es exacta. Se modela el tráfico futuro X como una variable normal centrada en la proyección, con el error típico de la proyección σ como desviación estándar: X ~ N(p, σ²). La probabilidad de pasarse de la capacidad es

$$P(X > C N) = 1 - \Phi\left(\frac{C N - p}{\sigma}\right) = \Phi\left(\frac{p - C N}{\sigma}\right)$$

usando la simetría de la distribución normal. Φ es su función de distribución acumulada (calculada como (1 + erf(z/√2))/2 en `risk.py`). Así es como el pronóstico construye intervalos de predicción, suponiendo errores normales [16]. La teoría de inventarios usa la misma fórmula para la probabilidad de quedarse sin existencias cuando la demanda es normal, y con ella dimensiona el stock de seguridad [20]: Aegis mantiene un "stock" de capacidad.

**Por qué una probabilidad y no solo "p > C·N".**
- Incluye **qué tan confiable es la proyección ahora mismo**: la misma p con tráfico ruidoso (σ grande) da más riesgo que con tráfico estable.
- El umbral tiene significado. Riesgo = 50% significa p = C·N exacto. Riesgo ≥ 70% significa p ≥ C·N + 0.52σ: la proyección está sobre la capacidad con margen.
- La misma fórmula sirve para cualquier número de pods: el motor de decisión pide el riesgo con los pods ya pedidos (para subir) y con uno menos (para bajar).

Ejemplo con C = 26 req/s, 1 pod, σ = 3: una proyección de 26 da 50%; 27.6 da 70% (Aegis pide un pod); 20 da 2%.

## 5. sigma: aprendido de los propios errores de la proyección

$$\sigma = \sqrt{2 \cdot \text{promedio}\left(\max(0, e)^2\right)}, \quad e = \text{tráfico real} - \text{proyección}$$

**De dónde sale.** Estimar la dispersión del pronóstico a partir de sus errores pasados es como los métodos de pronóstico obtienen su incertidumbre [16]. Aegis guarda cada proyección y, cuando llega su momento, la compara con el tráfico real. Usa los últimos 5 minutos.

**Por qué solo los errores positivos.** Solo es peligroso el tráfico que llega **por encima** de la proyección. Usar solo el lado peligroso es la idea de la semivarianza (riesgo a la baja) en finanzas [19]. Para errores simétricos, E[max(0, e)²] = σ²/2, así que el factor 2 devuelve el σ de siempre. Durante el desarrollo, usar los dos lados hacía saltar σ de 1 a 8–9 req/s cuando el tráfico paraba de golpe (la proyección quedaba muy por encima del tráfico real), lo que habría vuelto lento a Aegis los 5 minutos siguientes.

**Límites.** σ empieza en 2 hasta tener 6 errores, y nunca baja de 1 req/s, para que un tráfico muy estable no vuelva a Aegis demasiado confiado.

## 6. La regla de decisión: 70% para subir, 30% durante 60 s para bajar

Dos umbrales y un tiempo de espera son **histéresis**: el sistema no cambia de un lado a otro alrededor de un solo valor. El HPA hace lo mismo con sus ventanas de estabilización [1].

- **Sube** cuando el riesgo con los pods ya pedidos es ≥ 70%. Usar los pods pedidos (no solo los Ready) evita pedir más mientras un pod todavía está arrancando.
- **Baja** cuando el riesgo con **un pod menos** se mantiene bajo 30% durante 60 s. Preguntar "¿estaría seguro con uno menos?" en vez de "¿el riesgo es bajo ahora?" evita quitar el pod que es justamente la razón de que el riesgo sea bajo.

## Supuestos y límites

| Supuesto | Por qué se cumple aquí | Límite |
|---|---|---|
| La latencia depende sobre todo de las req/s | Todas las peticiones a `/api/books` cuestan lo mismo (un Scan completo) | Cargas mezcladas necesitarían una capacidad por tipo de petición |
| Los pods se reparten la carga parejo | Traefik reparte petición por petición | Sesiones pegajosas romperían C · N |
| Una conexión por petición | El tráfico de prueba la usa (`noConnectionReuse`) | Con keep-alive, las conexiones abiertas no cuentan las peticiones esperando |
| Errores más o menos normales | El umbral de 70% y el mínimo de σ dan margen | Colas muy pesadas necesitarían otra distribución |
| Tráfico con tendencia | Rampas y ondas | Un salto repentino sin tendencia previa no se puede anticipar; Aegis reacciona en T |

Referencias: ver [references.md](references.md).
