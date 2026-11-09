# Caso de negocio de Aegis

Documento de respaldo de la presentación «Aegis: caso de negocio» (21 diapositivas). Contiene el razonamiento, los cálculos y la fuente de cada cifra. Reemplaza la versión anterior, que establecía el problema con datos propios (37 % de fallas en la campaña de octubre) y cuyo modelo económico solo aplicaba a organizaciones que venden productos.

Cada cifra pertenece a una de tres categorías:

- **Medición propia:** campaña de 54 corridas del 2026-11-05 ([diseño](experiments/design.md), [resultados](experiments/results.md), datos en `docs/tests/`). Se usa **solo para medir el efecto de Aegis**, nunca para dimensionar el problema.
- **Fuente externa:** documentación oficial, organismos públicos, publicaciones revisadas por pares o encuestas de proveedores (estas últimas se identifican como tales). Referencias en la sección 12.
- **Estimación:** juicio del equipo o parámetro de cada organización; se declara y se muestra su efecto en la sensibilidad.

La investigación completa, con muestra, año y grado de confianza de cada cifra, está en [`reports/Evidencia externa caso de negocio Aegis.md`](../reports/Evidencia%20externa%20caso%20de%20negocio%20Aegis.md).

## 1. Cambios respecto de la versión anterior

| Elemento | Antes | Problema | Ahora |
|---|---|---|---|
| Magnitud del problema | 37 % de fallas medido en nuestro laboratorio | el problema se establecía con datos propios, y la cifra quedó desactualizada (con la sonda de salud corregida, el HPA por defecto falla 16,9 % en la misma rampa) | documentación oficial de AWS, Google Cloud y Kubernetes, y un estudio revisado por pares (sección 3) |
| Competencia | no se analizaba | | comparación con HPA, KEDA, Knative, PredictKube, escalado predictivo de AWS y Google, y Datadog (sección 5) |
| Modelo económico | ventas rescatadas × 53 % de abandono × margen minorista | solo aplicaba a quien vende; el 53 % mide visitas a páginas lentas, no peticiones fallidas | Aegis se plantea como proyecto Open Source, sin ingresos por licencias; el costo directo estimado para quien lo adopta es el tiempo de integración. El beneficio se calcula con minutos degradados evitados × picos al año × costo de un minuto degradado (secciones 9–11) |
| Valor no monetario | no se consideraba | | usuarios, carga operativa, energía, trazabilidad y cumplimiento (sección 8) |
| Evidencia | 32 corridas, un factor a la vez, sin aleatorizar | autoscaler confundido con la hora del día; solo contra el HPA por defecto | 54 corridas en bloques aleatorizados contra el HPA por defecto y uno afinado (sección 7) |
| Pods adicionales | 2,8 pods-minuto más por rampa | regla de bajada de 60 s fijos | regla de 15 a 60 s según el riesgo: igual o menor consumo que el HPA por defecto (sección 10) |
| Código de colores | HPA en rojo | el rojo se reserva para fallas | Aegis azul, HPA por defecto naranja, HPA afinado verde agua, tráfico gris, rojo solo para fallas |

## 2. Mercado (diapositiva 3)

| Cifra | Qué indica | Tipo | Fuente |
|---|---|---|---|
| 82 % de las organizaciones que utilizan contenedores ejecuta Kubernetes en producción (66 % en 2023) | Kubernetes es el estándar de facto | fuente | [1] |
| Más del 90 % de las organizaciones ejecutará contenedores en producción en 2027 (menos del 40 % en 2021) | el mercado sigue creciendo | fuente secundaria (Gartner citado por Google Cloud) | [2] |
| 66 % de las organizaciones que alojan IA generativa usa Kubernetes para la inferencia | también es la base de las cargas de IA | fuente | [1] |

Aegis se integra con el HPA, el escalador horizontal estándar de Kubernetes [3], ajustando su mínimo de réplicas sin sustituirlo.

## 3. El problema, con fuentes externas (diapositivas 2 y 4)

| Afirmación | Tipo | Fuente |
|---|---|---|
| «an autoscaler can only scale a group reactively, based on observed changes in load in real time… might not increase your application's capacity quickly enough» | documentación oficial | [4] |
| «dynamic scaling, which is reactive in nature» | documentación oficial | [5] |
| El HPA evalúa la métrica cada 15 s y no actúa mientras se mantenga a menos de un 10 % de su objetivo | documentación oficial | [3] |
| En el HPA de Kubernetes, «the first scaling-ups cause the majority of failed requests» | revisado por pares (banco de pruebas de 5 nodos; cualitativo) | [6] |
| La guía de Google para GKE recomienda reservar un 30 % de CPU ociosa mientras se inician nuevas réplicas | documentación oficial | [7] |
| La utilización media de CPU en clústeres Kubernetes es del 10 % (más de 2.100 organizaciones, datos de 2024) | encuesta de proveedor | [8] |

No existe en la literatura revisada una cifra fiable del tipo «el escalado reactivo falla un X % en los picos»: los porcentajes que circulan provienen de preprints y tesis con bancos de pruebas no comparables. Por eso el problema se establece cualitativamente con la documentación de los propios proveedores, y su costo con la recomendación oficial de sobreaprovisionar.

## 4. Cómo funciona Aegis (diapositivas 7 y 8)

**Subida (cada 5 s):**

```
p      = r + m × (T + lag)          demanda proyectada al momento en que un pod nuevo estaría listo
riesgo = Φ((p − C·N) / σ)           probabilidad de capacidad insuficiente
si riesgo ≥ 70 %: mínimo de réplicas del HPA + 1
```

r: peticiones por segundo actuales; m: tendencia de los últimos 30 s; T = 12 s de arranque de un pod (calibrado) y lag = 20 s de retraso de la medición; C = 22 req/s, capacidad calibrada de un pod; N: pods solicitados; σ: error de la proyección en los últimos 5 minutos (solo errores por debajo de la demanda real); Φ: distribución normal acumulada. Detalle en [formulas.md](formulas.md).

**Bajada:** Aegis calcula el riesgo con menos pods. Si permanece por debajo del 30 %, espera `15 s + 45 s × riesgo máximo / 30 %` y reduce directamente al menor número seguro de pods; cualquier ciclo con riesgo elevado reinicia la espera. La regla se inspira en el problema del alquiler de esquís [9]: la espera solo cubre el error de la proyección, que ya mira T + lag hacia adelante. Antes de adoptarla se simuló sobre 22 corridas registradas: entre 10 y 14 % menos pods-minuto sin aumentar el tiempo con capacidad insuficiente (`scripts/experiments/scale_down_sim.py`).

**Requisitos:** una calibración inicial de C y T, unos minutos de datos en vivo y ningún historial de días; los datos no salen del clúster.

## 5. Competencia (diapositivas 5 y 6)

| Herramienta | Escala según | ¿Anticipa? | Historial | Con el HPA | Explica cada decisión | Fuente |
|---|---|---|---|---|---|---|
| HPA | CPU o memoria | no | ninguno | es el HPA | no | [3] |
| KEDA (CNCF, graduado en 2023) | eventos, peticiones/s, horario | solo picos con horario fijo | ninguno | sí, lo gestiona | no | [10] |
| Knative (CNCF, graduado en 2025) | peticiones en curso | no; modo pánico sobre una ventana de 6 s | ninguno | utiliza su propio escalador | no | [11] |
| PredictKube | pronóstico con IA | sí, horas | 7 a 14 días; los datos salen del clúster | sí, vía KEDA | no | [12] |
| AWS y Google, predictivo | ciclos diarios de carga | sí, sobre máquinas virtuales | 1 a 14 días | no aplica a pods | no | [5], [4] |
| Datadog Kubernetes Autoscaling | uso de recursos | ajuste, sin anticipación de picos | servicio de Datadog | no: sustituye al HPA | no | [13] |
| **Aegis** | peticiones/s, cada 5 s | **sí, ~30 s** | **minutos de datos y una calibración; nada sale del clúster** | **sí, lo conserva** | **sí** | este repositorio |

**Diferenciación defendible:** entre las herramientas principales revisadas no se encontró otra que anticipe a nivel de pod sin días de historial, conserve el HPA y justifique cada decisión. La afirmación es «no encontrada entre las principales», no «única».

**Límites honestos:** KEDA y Knative ya escalan por peticiones por segundo; ante picos abruptos nadie anticipa (Aegis pidió el 2º pod unos 12 s después de que la demanda superara un pod; Knative no se midió); para picos con horario fijo, KEDA por horario o el escalado predictivo de la nube anticipan más; KEDA y Knative son proyectos graduados de la CNCF y Aegis es un desarrollo reciente. Aegis escala pods y se complementa con Karpenter o Cluster Autoscaler para la capacidad de nodos.

## 6. Diseño experimental (diapositivas 9 a 12)

Diseño de bloques completos aleatorizados con tratamientos factoriales 3 × 3 [14]: 3 autoscalers (Aegis, HPA por defecto con CPU al 70 %, HPA afinado con CPU al 50 % y reducción en 60 s) × 3 cargas (rampa, pico, olas) × 6 bloques = 54 corridas en orden aleatorio con semilla fija, registradas antes de la primera corrida. Métrica principal: porcentaje de peticiones fallidas medido por k6. Análisis: ANOVA con bloques, 6 contrastes corregidos con Holm [15], respaldo por rangos donde los residuos no son normales (el pico). Plan completo en [design.md](experiments/design.md).

| Carga | Perfil (escalado a C = 22 req/s) | Cruza la capacidad de un pod |
|---|---|---|
| Rampa | de 5 a 46 req/s en 2 min, 1 min sostenido | a los 80 s |
| Pico | de 5 a 41 req/s en 5 s, 90 s sostenido | a los 33 s |
| Olas | hasta 28 y 46 req/s, con 2 min de tráfico bajo después de cada una | a los 79 s |

## 7. Evidencia (diapositivas 13 y 14)

Peticiones fallidas, media de 6 corridas (en la diapositiva, cada corrida se muestra como un punto):

| Carga | Aegis | HPA por defecto | HPA afinado | Contrastes (p de Holm) |
|---|---|---|---|---|
| Rampa | **1,9 %** | 16,9 % (9,1×) | 15,4 % (8,3×) | 0,026 y 0,030 |
| Pico | **5,6 %** | 26,7 % (4,7×) | 24,9 % (4,4×) | 0,001 y 0,0001 (rangos) |
| Olas | **1,4 %** | 3,7 % (no demostrado) | 7,1 % (5,0×) | 0,18 y 0,019 |

Aegis tuvo menos fallas en 5 de las 6 comparaciones registradas. Con la mediana la conclusión no cambia (rampa 0,9 % frente a 14,4 % y 12,9 %; pico 5,5 % frente a 19,9 % y 23,4 %). En un análisis de sensibilidad no registrado (t pareado sobre log(1 + %)) los mismos 5 contrastes son significativos; con el t pareado sin transformar, 2 son significativos y 3 quedan en p = 0,063.

Métricas secundarias (exploratorias, sin corrección): tiempo degradado de 58 s frente a 123 y 129 s en la rampa, y 46 s frente a 123 y 113 s en el pico; solicitud del 2º pod a los 77 s frente a 148 y 138 s en la rampa; pods-minuto inferiores al HPA por defecto en las tres cargas (−27 % en las olas) y equivalentes al HPA afinado salvo en el pico (13,9 frente a 12,3). Detalle en [results.md](experiments/results.md).

## 8. Valor no monetario (diapositiva 15)

| Dimensión | Evidencia externa | Tipo | Fuente |
|---|---|---|---|
| Retención de usuarios | 32 % de los consumidores abandonaría una marca de su preferencia tras una única mala experiencia (49 % en América Latina); 15.000 personas | encuesta, intención declarada, verificada en fuentes secundarias | [16] |
| Carga operativa | Google limita el trabajo operativo reactivo («toil») al 50 % del tiempo de cada ingeniero y advierte que su exceso conduce al agotamiento | publicación de Google | [17] |
| Eficiencia energética | los centros de datos consumieron cerca de 415 TWh en 2024, el 1,5 % de la electricidad mundial | organismo internacional | [18] |
| Trazabilidad y cumplimiento | el reglamento DORA exige a las entidades financieras de la UE gestionar y notificar los incidentes graves de TIC | regulación | [19] |

No se midieron alertas, consumo energético ni abandono de usuarios: la relación entre menor tiempo degradado y estos beneficios es una inferencia.

## 9. Modelo económico (diapositivas 16, 18 y 19)

Para las instrucciones de edición de la presentación, consulta la [guía del modelo económico Open Source](modelo-economico-open-source.md).

**Modelo de adopción:** Aegis se plantea como software Open Source, al estilo de Prometheus, para que las organizaciones lo adopten sin pagar una licencia o suscripción. No se propone vender Aegis; el costo directo considerado para una organización es el tiempo de trabajo necesario para integrarlo en su ecosistema. El repositorio todavía no contiene un archivo de licencia, por lo que debe definirse y añadirse una licencia antes de afirmar que la distribución ya está formalmente licenciada como Open Source.

```
valor anual = minutos degradados evitados por pico × picos al año × costo de un minuto degradado
```

| Factor | Valor | Tipo |
|---|---|---|
| Minutos degradados evitados por pico | 0,76 min: promedio de rampa (65 s), pico (77,5 s) y olas (−5,8 s, no significativo) frente al HPA por defecto | medición propia, métrica secundaria; se trata como estimación |
| Picos al año | parámetro de cada organización | estimación |
| Costo de un minuto degradado | parámetro de cada organización, suma de los componentes que le apliquen | estimación |

**Componentes del costo por minuto, por tipo de organización:**

| Organización | Componentes |
|---|---|
| Comercio en línea | ventas por minuto × margen × proporción de compras no concretadas; clientes que no regresan |
| Software como servicio | créditos por incumplimiento de SLA (AWS y Google reembolsan entre 10 y 100 % de la factura según la disponibilidad, solo por indisponibilidad) [20]; cancelación de clientes |
| Plataforma interna | personas afectadas × costo de su hora ÷ 60; horas del equipo que atiende el incidente |
| Banca y sector público | sanciones y obligaciones de notificación (por ejemplo, DORA [19]); atención a clientes o ciudadanos afectados |

El modelo anterior (ventas recuperadas × margen) corresponde solo al primer caso. Que el costo de una interrupción no se limita a los ingresos lo respalda Splunk y Oxford Economics: además de los ingresos perdidos, las empresas del Global 2000 reportan en promedio 22 M$ anuales en sanciones regulatorias y 16 M$ en penalizaciones de SLA (encuesta de proveedor, 2.000 ejecutivos) [21].

## 10. Costos (diapositiva 17)

| Concepto | Cálculo | Valor | Tipo |
|---|---|---|---|
| Tiempo de integración inicial | Estimación de 16 h, equivalente a 2 jornadas de 8 h | **16 h** | estimación teórica |
| Costo de la hora de trabajo | Supuesto del modelo | **30 $/h** | supuesto |
| **Costo de integración, una vez** | 16 h × 30 $/h | **480 $** | estimación teórica |
| Licencia o suscripción de Aegis | No se contempla cobro por uso | **0 $** | modelo de adopción propuesto |
| Mantenimiento e infraestructura incremental | No incluidos en este cálculo; dependen de la operación de cada organización | — | fuera del alcance del modelo |

El cálculo asume que la organización ya cuenta con un clúster Kubernetes operativo y recursos para ejecutar Aegis. El costo de 480 $ representa únicamente el esfuerzo inicial estimado de integración; no es una tarifa que se pague al proyecto.

## 11. Punto de equilibrio y sensibilidad (diapositivas 18 y 20)

```
costo por minuto degradado de equilibrio, primer año = 480 $ ÷ (minutos evitados por pico × picos al año)
```

| Picos al año | Costo por minuto degradado necesario para recuperar la integración en el primer año |
|---|---|
| 52 (semanal) | **12,15 $/min** |
| 156 (tres por semana) | **4,05 $/min** |
| 365 (diario) | **1,73 $/min** |

Los valores usan la estimación experimental de 0,76 minutos degradados evitados por pico. Con 52 picos al año, si Aegis evitara solo la mitad de ese tiempo (0,38 min por pico), el punto de equilibrio sería **24,29 $/min**. No se incluyen costos recurrentes ni infraestructura incremental.

**Referencias de contraste** (no entran en el cálculo, son interrupciones totales y encuestas autodeclaradas): 4.537 $ por minuto de incidente en empresas de más de 1.000 empleados (PagerDuty 2024, 500 líderes de TI, encuesta de proveedor) [22]; más del 90 % de las empresas medianas y grandes declara que una hora de interrupción cuesta más de 300.000 $ (ITIC 2024, más de 1.000 empresas) [23]. No existe una cifra publicada de la relación entre el costo de un minuto degradado y el de un minuto de interrupción total; con picos semanales, el costo de un minuto degradado tendría que superar aproximadamente **12 $** para recuperar el esfuerzo de integración en el primer año.

## 12. Robustez y riesgos (diapositiva 20)

| Medición propia | Fuente externa | Estimación |
|---|---|---|
| Fallas, tiempo degradado y pods-minuto (54 corridas) | documentación de AWS, Google y Kubernetes; IEA; Google SRE | 16 h de integración inicial y tarifa supuesta de 30 $/h; mantenimiento e infraestructura incremental excluidos |
| 0,76 minutos degradados evitados por pico | encuestas de proveedores, identificadas: CAST AI, Splunk, PagerDuty, PwC | picos al año y costo por minuto de cada organización |
| | | representatividad del laboratorio respecto de producción |

Riesgos principales:

- **Representatividad del laboratorio:** un nodo, pods de 60m de CPU, como máximo 3 réplicas, carga sintética. Si Aegis evitara la mitad de los minutos degradados, el equilibrio semanal pasa de 12,15 a 24,29 $/min.
- **Deriva de capacidad durante la campaña:** C medida pasó de 22 a 30 y a 24 req/s; se mantuvo C = 22 como establece el plan, lo que hace a Aegis más conservador (registro de desviaciones en [design.md](experiments/design.md)).
- **Picos abruptos:** Aegis no los anticipa; reduce las fallas al reaccionar antes que el HPA, pero no las evita.
- **Métricas secundarias:** el tiempo degradado y los pods-minuto no tienen corrección por comparaciones múltiples.
- **Regla de bajada elegida sobre trazas de la campaña de octubre con las mismas cargas:** su ventaja en costo podría ser menor con tráfico no visto.

## 13. Cifras retiradas

- **37 % de fallas sin Aegis** (campaña de octubre): dato propio usado para establecer el problema y desactualizado tras corregir la sonda de salud.
- **53 % de abandono** (Google/SOASTA 2016–2017) como proporción de compradores perdidos: mide visitas a páginas lentas, no peticiones fallidas.
- **Margen bruto minorista de 33,18 %** como factor universal: aplica solo a comercio; ahora es un componente opcional del costo por minuto.
- **Gartner, 5.600 $ por minuto** (2014): sin metodología verificable y con 12 años de antigüedad.
- **Porcentajes de violación de SLO del HPA** (15,3 % y 53 %): provienen de un preprint y una tesis no comparables.
- Las cifras retiradas en la versión anterior por no ser verificables (TracResearch, Akamai/SpeedCurve 2025, Catchpoint 2025, «AWS EKS 2026») siguen retiradas.

## 14. Fuentes

1. Cloud Native Computing Foundation, Annual Cloud Native Survey, 20 de enero de 2026. https://www.cncf.io/reports/the-cncf-annual-cloud-native-survey/
2. C. Goldberg y D. Bradstock, «Google is a Leader in the 2023 Gartner Magic Quadrant for Container Management», Google Cloud Blog, 26 de septiembre de 2023. https://cloud.google.com/blog/products/containers-kubernetes/a-leader-in-2023-gartner-magic-quadrant-for-container-management
3. The Kubernetes Authors, «Horizontal Pod Autoscaling», documentación oficial. https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/
4. Google Cloud, «Scaling based on predictions» (Predictive autoscaling), documentación de Compute Engine. https://docs.cloud.google.com/compute/docs/autoscaler/predictive-autoscaling
5. Amazon Web Services, «Predictive scaling for Amazon EC2 Auto Scaling», documentación oficial. https://docs.aws.amazon.com/autoscaling/ec2/userguide/ec2-auto-scaling-predictive-scaling.html
6. T.-T. Nguyen, Y.-J. Yeom, T. Kim, D.-H. Park y S. Kim, «Horizontal Pod Autoscaling in Kubernetes for Elastic Container Orchestration», Sensors 20(16):4621, 2020. https://pmc.ncbi.nlm.nih.gov/articles/PMC7471989
7. Google Cloud, «Best practices for running cost-optimized Kubernetes applications on GKE». https://docs.cloud.google.com/architecture/best-practices-for-running-cost-effective-kubernetes-applications-on-gke
8. CAST AI, «2025 Kubernetes Cost Benchmark Report», 5 de marzo de 2025. https://cast.ai/press-release/new-kubernetes-cost-benchmark-report-reveals-persistent-cloud-waste/
9. A. R. Karlin, M. S. Manasse, L. Rudolph y D. D. Sleator, «Competitive Snoopy Caching», Algorithmica 3, pp. 79–119, 1988.
10. KEDA, documentación (escaladores cron y PredictKube) y anuncio de graduación en la CNCF, agosto de 2023. https://keda.sh/docs/2.18/scalers/cron/ · https://www.cncf.io/news/2023/08/22/itops-times-keda-graduates-from-cncf/
11. Knative, «Additional autoscaling configuration for KPA» y anuncio de graduación en la CNCF, 8 de octubre de 2025. https://knative.dev/docs/serving/autoscaling/kpa-specific/ · https://www.cncf.io/announcements/2025/10/08/cloud-native-computing-foundation-announces-knatives-graduation/
12. KEDA, «PredictKube scaler». https://keda.sh/docs/2.18/scalers/predictkube/
13. Datadog, «Kubernetes Autoscaling», documentación. https://docs.datadoghq.com/containers/autoscaling
14. R. A. Fisher, *The Design of Experiments*, Oliver and Boyd, 1935; D. C. Montgomery, *Design and Analysis of Experiments*, 9.ª ed., Wiley, 2017.
15. S. Holm, «A Simple Sequentially Rejective Multiple Test Procedure», Scandinavian Journal of Statistics 6(2), pp. 65–70, 1979.
16. PwC, «Experience is everything: Here's how to get it right», 2018. https://www.pwc.com/cb/en/services/consulting/pdf/customer-experience-placemat.pdf
17. B. Beyer et al., *Site Reliability Engineering*, cap. 5 «Eliminating Toil», Google, 2016. https://sre.google/sre-book/eliminating-toil/
18. International Energy Agency, *Energy and AI*, 2025. https://www.iea.org/reports/energy-and-ai
19. Reglamento (UE) 2022/2554 sobre la resiliencia operativa digital del sector financiero (DORA). https://eur-lex.europa.eu/eli/reg/2022/2554/oj/eng
20. Amazon Compute Service Level Agreement; Google Compute Engine Service Level Agreement. https://aws.amazon.com/compute/sla/ · https://cloud.google.com/compute/sla
21. Splunk y Oxford Economics, «The Hidden Costs of Downtime», junio de 2024. https://newsroom.cisco.com/c/r/newsroom/en/us/a/y2024/m06/conf24-splunk-report-shows-downtime-costs-global-2000-companies-400b-annually.html
22. PagerDuty, «Cost of Incidents» study, 2024. https://pagerduty.com/newsroom/study-cost-of-incidents
23. ITIC, «2024 Hourly Cost of Downtime Survey». https://itic-corp.com/?p=3152
