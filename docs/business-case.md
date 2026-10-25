# Caso de negocio de Aegis

Documento de respaldo de la presentación «Aegis: caso de negocio» (12 diapositivas). Reemplaza el modelo económico de `business_case.md` y del PDF del Sprint 0, que no mostraban de dónde salían sus números.

Cada número de este documento es de uno de tres tipos:

- **Medido:** de nuestra campaña de 32 corridas del 2026-10-25 (`docs/tests/`).
- **Fuente:** de un estudio, organismo oficial o proveedor, citado en la sección 9 con su enlace.
- **Estimación:** juicio del equipo sin fuente pública; se dice así y se muestra su efecto.

## 1. Evaluación de realismo del modelo anterior

El modelo anterior (ROI de 105 % y 720 %, y la primera versión de esta presentación, con 103 % y 761 %) dependía de valores sin respaldo. Esta tabla resume qué se conservó y qué se cambió:

| Elemento | Antes | Problema | Ahora |
|---|---|---|---|
| Ingreso de la empresa | 50 M $/año | empresa inventada | ya no se supone: es el dato de entrada de cada empresa (ventas durante sus picos) |
| Tráfico en el pico | 3 veces el promedio | supuesto sin fuente | eliminado: el modelo usa directamente las ventas durante los picos |
| Usuarios que reintentan tras un error | 50 % | supuesto sin fuente | 53 % de abandono pasados 3 s (Akamai 2017, Google): fuente |
| Picos al año | 200 | supuesto sin fuente | eliminado: queda dentro de «ventas durante los picos al año» |
| Ahorro FinOps de 100.000 $ | colchón ocioso del 30 % al 10 % | contradicho por nuestros datos: Aegis usa más pods que el HPA durante un pico | eliminado |
| Horas de implementación | 100.000 $ sin desglose | sin cálculo | 160 h × 93,26 $/h (BLS); las horas siguen siendo estimación y se da su rango |
| Cifras de la industria | TracResearch, Akamai/SpeedCurve 2025, Catchpoint 2025, AWS EKS 2026 | no verificables en su fuente original | retiradas; sección 8 |

## 2. Por qué solo Kubernetes (diapositiva 3)

| Cifra | Qué dice | Tipo | Fuente |
|---|---|---|---|
| 82 % de quienes usan contenedores corre Kubernetes en producción (66 % en 2023) | Kubernetes es el estándar de facto para correr contenedores | fuente | [11] |
| Más del 90 % de las organizaciones correrá aplicaciones en contenedores en producción en 2027 (menos del 40 % en 2021) | el mercado de contenedores sigue creciendo | fuente (Gartner, cita textual en [12]) | [12] |
| 66 % de las organizaciones que alojan IA generativa usa Kubernetes para algunas o todas sus cargas de inferencia | también es la base de las nuevas cargas de IA | fuente | [11] |
| El HPA es el escalador horizontal estándar de Kubernetes | Aegis se integra con él (ajusta `minReplicas` o le entrega una métrica) sin reemplazar el scheduler ni cambiar cómo se despliega | fuente | [4] |

Construir sobre Kubernetes permite que Aegis llegue a la mayoría de las organizaciones que usan contenedores con un solo punto de integración, el HPA, que ya usan.

## 3. El problema (diapositivas 2, 4 y 5)

| Cifra | Qué mide | Tipo | Fuente |
|---|---|---|---|
| −7 % de conversión por cada 100 ms de demora | móvil, unos 10 mil millones de visitas a retailers | fuente | [1] |
| 53 % de los visitantes móviles se va si la página tarda más de 3 s | abandono por demora | fuente | [1], [2] |
| +8,4 % de conversiones en retail al ganar 0,1 s | móvil, 37 marcas, más de 30 millones de sesiones | fuente | [3] |
| El HPA revisa la métrica cada 15 s y no actúa dentro de una tolerancia del 10 % | funcionamiento del HPA | fuente | [4] |
| Aegis pide el 2º pod en el segundo 73,5 a 74,5; el HPA, en el 116 a 145 (el tráfico supera un pod en el 80) | rampa, 5 corridas por lado | medido | `docs/tests/comparison.md` |
| 37,1 % de peticiones fallidas sin Aegis en la rampa (34,7 a 40,1 %) | 5 corridas | medido | `docs/tests/test3-hpa-baseline/` |
| 10 % de uso medio de CPU en clústeres Kubernetes | más de 2.100 organizaciones, datos de 2024 | fuente | [5] |

## 4. La evidencia medida (diapositiva 6)

| Carga | Aegis | Solo HPA | Diferencia |
|---|---|---|---|
| Rampa (5 a 46 req/s en 2 min) | **2,5 %** (0,48 a 4,69) | 37,1 % (34,7 a 40,1) | 34,6 puntos, 15 veces menos |
| Pico (5 a 41 req/s en 5 s) | **13,3 %** (11,7 a 16,1) | 54,8 % (51,9 a 61,0) | 41,5 puntos, 4 veces menos |
| Pods-minuto por rampa | 8,53 | 5,74 | 2,79 más con Aegis |

Medido por k6 desde el cliente, media de 5 corridas por fila. Metodología: `docs/tests/README.md`; límites: `docs/limitations.md`.

## 5. El modelo económico (diapositivas 7 a 10)

### 5.1 Beneficio

```
beneficio anual = V × Δf × p
```

| Símbolo | Significado | Valor | Tipo y origen |
|---|---|---|---|
| V | ventas que pasan por el servicio durante sus picos de tráfico, en un año | dato de cada empresa | entrada |
| Δf | peticiones que dejan de fallar con Aegis: 37,12 % menos 2,50 % | 0,3462 | medido, rampa, 5 + 5 corridas |
| p | parte de los usuarios que se pierde cuando una página falla o tarda más de 3 s | 0,53 | fuente [1], [2] |
| Δf × p | dólares protegidos por cada dólar vendido durante los picos | **0,1835** | cálculo |

Por qué p = 0,53 es un piso: nuestras peticiones «fallidas» son errores o esperas de 10 s (el límite de k6); el 53 % se refiere a esperas de solo 3 s. Además no se cuenta la pérdida por lentitud en las peticiones que sí responden (la −7 % por cada 100 ms) ni el daño de marca. El cálculo es conservador.

Para el pico abrupto, Δf = 0,4147 y Δf × p = 0,2198; se usa la rampa porque es el caso donde Aegis puede anticiparse.

### 5.2 Costos

| Concepto | Cálculo | Valor | Tipo y origen |
|---|---|---|---|
| Hora de ingeniería | 135.980 $/año ÷ 2.080 h = 65,38 $/h; ÷ 0,701 porque el salario es el 70,1 % del costo del empleador | 93,26 $/h | fuente [6], [7] |
| Implementación, una vez | 160 h × 93,26 $ | **14.922 $** | horas: estimación (rango 80 a 320 h) |
| Mantenimiento, por año | 4 h/mes × 12 × 93,26 $ | 4.476 $ | horas: estimación |
| Pod de Aegis encendido todo el año | límite de 200m CPU en `kubernetes/aegis/deployment.yaml`; Fargate lo cobra en su tamaño mínimo, 0,25 vCPU y 0,5 GB: (0,25 × 0,04048 + 0,5 × 0,004445) $/h × 8.760 h | 108 $ | repositorio + fuente [8] |
| **Operación, por año** | 4.476 + 108 | **4.585 $** | |
| Pods extra durante un pico | medido: 2,79 pods-minuto más por rampa con un pico de 3 pods. Cota superior: 100 pods de 4 vCPU y 8 GB son 93 pods-minuto × 0,00329 $ | **≤ 0,31 $ por pico** | medido + fuente [8] |

Más del 99 % del costo anual es tiempo de personas; pedir capacidad antes casi no cuesta.

### 5.3 Punto de equilibrio

| Indicador | Cálculo | Valor |
|---|---|---|
| Equilibrio en operación (desde el año 2) | 4.585 ÷ 0,1835 | **24.989 $** de ventas en picos al año |
| Equilibrio del año 1 (con implementación) | (14.922 + 4.585) ÷ 0,1835 | **106.321 $** |
| Equivalencia del equilibrio en operación | 24.989 ÷ (4 min × 52 semanas) | 120 $ por minuto en un pico de 4 min por semana |

### 5.4 Tres escenarios (diapositiva 10)

| Ventas en picos al año (V) | Beneficio anual (0,1835 × V) | ROI año 1 | ROI desde el año 2 | Recuperación |
|---|---|---|---|---|
| 100.000 $ | 18.346 $ | −6 % | 300 % | 13 meses |
| 250.000 $ | 45.866 $ | 135 % | 900 % | 4,3 meses |
| 1.000.000 $ | 183.465 $ | 841 % | 3.902 % | 1 mes |

ROI año 1 = (beneficio − 14.922 − 4.585) ÷ (14.922 + 4.585). ROI desde el año 2 = (beneficio − 4.585) ÷ 4.585. Recuperación = 14.922 ÷ ((beneficio − 4.585) ÷ 12).

Referencia de escala (no entra en el cálculo): en las horas pico de Cyber Monday 2024 los consumidores de EE. UU. gastaron en línea 15,8 millones de dólares por minuto [9].

### 5.5 Sensibilidad

| Si cambia | Efecto |
|---|---|
| Implementación de 80 h | equilibrio del año 1: 65.655 $ |
| Implementación de 320 h | equilibrio del año 1: 187.653 $ |
| La brecha de fallas es la mitad (por ejemplo, un HPA afinado) | equilibrio en operación: 49.978 $ |
| Se usa el pico abrupto en vez de la rampa (Δf × p = 0,2198) | equilibrio en operación: 20.860 $ |

### 5.6 Cómo calcularlo para una empresa

1. Estimar V: las ventas que pasan por el servicio durante los momentos en que el tráfico sube más rápido de lo que el HPA alcanza a escalar (campañas, horarios, lanzamientos).
2. Beneficio anual = 0,1835 × V.
3. Ajustar las horas de implementación y mantenimiento a su equipo; el costo por hora sale del BLS o del salario local.

## 6. Qué tan sólido es (diapositiva 11)

| Medido | Fuente oficial | Estimación |
|---|---|---|
| Fallas: 2,5 % contra 37,1 % | 53 % de abandono pasados 3 s [1], [2] | 160 h de implementación |
| Pedido del pod: 6 s antes contra 36 a 65 s tarde | 93,26 $ por hora de ingeniería [6], [7] | 4 h al mes de operación |
| 2,79 pods-minuto extra por pico | precios de AWS Fargate [8] | que el laboratorio se parezca a producción |

Riesgos principales:

- **El laboratorio no es producción:** un nodo, pods de 60m de CPU, el HPA por defecto (CPU al 70 %) y un timeout de 10 s en k6. Un HPA afinado (objetivo más bajo, métrica de peticiones) reduciría la brecha; la literatura académica también reporta grandes mejoras de los escaladores proactivos frente al HPA en picos [10], pero no se usa ese número en el cálculo.
- **Picos sin tendencia:** si el tráfico sube en menos de unos 40 s, Aegis reduce las fallas de 54,8 % a 13,3 % pero no las evita.
- **Conexión por la Custom Metrics API:** la decisión llega de 3 a 12 s tarde (9,5 s de media) y las fallas suben a 20,2 %; se recomienda que Aegis escriba `minReplicas`.

## 7. Diapositivas y su contenido

| N.º | Título | Contenido |
|---|---|---|
| 1 | Aegis | portada: la capacidad llega antes que el tráfico |
| 2 | Unas décimas de segundo valen ventas | −7 %, +8,4 %, 53 % |
| 3 | Por qué Kubernetes | 82 % en producción, +90 % de organizaciones con contenedores en 2027, 66 % para inferencia de IA |
| 4 | El HPA pide el pod cuando el servicio ya se rompió | línea de tiempo medida: s 74 contra s 116 a 145 |
| 5 | Hoy se elige entre estas dos | 37 % de fallas o 10 % de uso de CPU |
| 6 | La evidencia | 15 veces menos fallas; barras de rampa y pico |
| 7 | De cada dólar que pasa por un pico, Aegis protege 18 centavos | 0,346 × 0,53 = 0,18 |
| 8 | Lo que cuesta es la ingeniería, no los pods | 14.900 $, 4.600 $/año, ≤ 0,31 $ por pico |
| 9 | Se paga desde 25.000 $ al año vendidos en picos | gráfico de equilibrio; 120 $/min |
| 10 | Cuanto más se vende en los picos, antes se paga | escenarios de 100.000, 250.000 y 1.000.000 $ |
| 11 | De dónde sale cada número | medido, fuente oficial, estimación; riesgos |
| 12 | Todo número tiene su origen | fuentes |

Cada diapositiva lleva en sus notas del presentador el razonamiento completo.

## 8. Cifras retiradas

No se encontraron en una fuente primaria verificable: «10x más frecuentes las degradaciones» (TracResearch, 2025); «28 % de abandono permanente contra 9 %» (Akamai/SpeedCurve, 2025); «42 % de directivos» y «51 % pierde más de 1 M $ al mes» (Catchpoint, 2025); «AWS EKS, 2026» como fuente de tiempos de arranque. También se retiraron los supuestos sin respaldo del modelo anterior (sección 1).

## 9. Fuentes

1. Akamai, «Akamai Releases Spring 2017 State of Online Retail Performance Report», 18 de abril de 2017. https://www.ir.akamai.com/node/12716
2. Google, «The Need for Mobile Speed» y «Mobile site load time statistics», Think with Google. https://www.thinkwithgoogle.com/consumer-insights/consumer-trends/mobile-site-load-time-statistics/
3. Deloitte para Google, «Milliseconds Make Millions», 24 de marzo de 2020. https://www.deloitte.com/ie/en/services/consulting/research/milliseconds-make-millions.html
4. The Kubernetes Authors, «Horizontal Pod Autoscaling», documentación oficial. https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/
5. CAST AI, «2025 Kubernetes Cost Benchmark Report», 5 de marzo de 2025. https://cast.ai/press-release/new-kubernetes-cost-benchmark-report-reveals-persistent-cloud-waste/
6. U.S. Bureau of Labor Statistics, «Software Developers», Occupational Outlook Handbook (mediana de mayo de 2025: 135.980 $). https://www.bls.gov/ooh/computer-and-information-technology/software-developers.htm
7. U.S. Bureau of Labor Statistics, «Employer Costs for Employee Compensation», diciembre de 2025 (salario = 70,1 % del costo en el sector privado). https://www.bls.gov/news.release/ecec.htm
8. Amazon Web Services, «AWS Fargate Pricing», US East (N. Virginia), Linux/x86: 0,000011244 $ por vCPU-segundo (0,04048 $/h) y 0,000001235 $ por GB-segundo (0,004445 $/h), mínimo de 1 minuto. https://aws.amazon.com/fargate/pricing/
9. Adobe, «Cyber Monday recap», 3 de diciembre de 2024. https://news.adobe.com/news/2024/12/120324-adi-cyber-monday-recap
10. B. Choi, J. Park, C. Lee y D. Han, «pHPA: A Proactive Autoscaling Framework for Microservice Chain», 5th Asia-Pacific Workshop on Networking (APNet), 2021. https://doi.org/10.1145/3469393.3469401
11. Cloud Native Computing Foundation, «Kubernetes Established as the De Facto "Operating System" for AI as Production Use Hits 82% in 2025 CNCF Annual Cloud Native Survey», 20 de enero de 2026. https://www.cncf.io/announcements/2026/01/20/kubernetes-established-as-the-de-facto-operating-system-for-ai-as-production-use-hits-82-in-2025-cncf-annual-cloud-native-survey/ · informe: https://www.cncf.io/reports/the-cncf-annual-cloud-native-survey/
12. C. Goldberg y D. Bradstock, «Google is a Leader in the 2023 Gartner Magic Quadrant for Container Management», Google Cloud Blog, 26 de septiembre de 2023 (cita textual de la predicción de Gartner). https://cloud.google.com/blog/products/containers-kubernetes/a-leader-in-2023-gartner-magic-quadrant-for-container-management

Lecturas de contexto, no usadas en el cálculo: R. Kohavi, D. Tang y Y. Xu, *Trustworthy Online Controlled Experiments*, Cambridge University Press, 2020 (cap. «Speed Matters»); E. Schurman y J. Brutlag, «Performance Related Changes and their User Impact», O’Reilly Velocity, 2009; Uptime Institute, «Annual Outage Analysis 2025»; ITIC, «2024 Hourly Cost of Downtime Survey».
