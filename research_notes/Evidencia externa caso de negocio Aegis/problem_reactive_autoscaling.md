# El problema: el autoscaling reactivo (HPA / basado en CPU) llega tarde a los picos de tráfico

Investigado el 2026-11-05. Las citas textuales se dejan en inglés original. Escala de fiabilidad usada: **A** = documentación oficial o artículo revisado por pares; **B** = informe de analista/industria con metodología declarada; **C** = informe de proveedor con interés comercial, o preprint sin revisión por pares; **D** = no trazable (no usar).

## 1. Qué dice la documentación oficial sobre la mecánica de reacción del HPA

### Takeaway
La documentación oficial de Kubernetes define un bucle de control discreto (15 s), una banda muerta de tolerancia del 10 %, un periodo de 5 min en el que se ignora la CPU de los pods que arrancan, un retraso de readiness de 30 s, un tope de escalado hacia arriba (100 % o 4 pods cada 15 s) y una estabilización de 300 s para escalar hacia abajo. AWS y Google Cloud describen el autoscaling estándar como "reactive in nature" y presentan el escalado predictivo como remedio para el lag. Es la evidencia de mayor fiabilidad (A), pero es cualitativa: describe el mecanismo, no mide un daño.

### Cited Findings
- **Periodo de sincronización de 15 s (A, documentación oficial vigente):** "Kubernetes implements horizontal pod autoscaling as a control loop that runs intermittently (it is not a continuous process). The interval is set by the `--horizontal-pod-autoscaler-sync-period` parameter to the kube-controller-manager (and the default interval is 15 seconds)." — [Kubernetes docs, Horizontal Pod Autoscaling](https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/)
- **Tolerancia del 10 %:** "The control plane skips any scaling action if the ratio is sufficiently close to 1.0 (within a configurable tolerance, 0.1 by default)." y "If you don't set this field, the HPA applies the default cluster-wide tolerance of 10%." — [Kubernetes docs, HPA](https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/)
- **Estabilización de 300 s al escalar hacia abajo:** "For scaling down the stabilization window is _300_ seconds (or the value of the `--horizontal-pod-autoscaler-downscale-stabilization` command line option, if provided)." — [Kubernetes docs, HPA](https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/)
- **Tope por defecto al escalar hacia arriba:** "There are 2 policies where 4 pods or a 100% of the currently running replicas may at most be added every 15 seconds till the HPA reaches its steady state." Para escalar hacia arriba no hay ventana de estabilización ("the target is scaled up immediately"). — [Kubernetes docs, HPA](https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/)
- **Arranque de pods: periodo de inicialización de CPU de 5 min y retraso de readiness de 30 s:** "`--horizontal-pod-autoscaler-cpu-initialization-period` (default: 5 minutes) This defines the time window after a Pod starts during which its CPU usage is ignored unless: The Pod is in a `Ready` state and the metric sample was taken entirely during the period it was `Ready`." y "`--horizontal-pod-autoscaler-initial-readiness-delay` (default: 30 seconds)". — [Kubernetes docs, HPA](https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/)
- **Amortiguación conservadora:** "if any not-yet-ready pods were present, and the workload would have scaled up without factoring in missing metrics or not-yet-ready pods, the controller conservatively assumes that the not-yet-ready pods are consuming 0% of the desired metric, further dampening the magnitude of a scale up." — [Kubernetes docs, HPA](https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/)
- **Metrics Server:** "The `metrics.k8s.io` API is usually provided by an add-on named Metrics Server, which needs to be launched separately." La página del HPA no indica la resolución de Metrics Server. — [Kubernetes docs, HPA](https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/)
- **Intervalo de scraping de 60 s (fuente revisada por pares, no la documentación):** "The default scraping period is 60 s" para Kubernetes Resource Metrics, es decir, el valor de CPU que ve el HPA puede tener hasta ~1 min de antigüedad. — [Nguyen et al., Sensors 20(16):4621, 2020](https://pmc.ncbi.nlm.nih.gov/articles/PMC7471989)
- **AWS (A, documentación oficial):** "Predictive scaling can help you scale faster by launching capacity in advance of forecasted load, compared to using only dynamic scaling, which is reactive in nature." Señala como caso de uso las "Applications that take a long time to initialize, causing a noticeable latency impact on application performance during scale-out events", y añade: "You don't have to wait for dynamic scaling to react to changing traffic." — [AWS EC2 Auto Scaling User Guide, Predictive scaling](https://docs.aws.amazon.com/autoscaling/ec2/userguide/ec2-auto-scaling-predictive-scaling.html)
- **AWS sobre el sobreaprovisionamiento:** "Predictive scaling can also potentially save you money on your EC2 bill by helping you avoid the need to over provision capacity." — [AWS docs](https://docs.aws.amazon.com/autoscaling/ec2/userguide/ec2-auto-scaling-predictive-scaling.html)
- **Google Cloud (A, documentación oficial):** "an autoscaler can only scale a group reactively, based on observed changes in load in real time." y "if your application takes a few minutes or more to initialize, adding instances in response to real-time changes might not increase your application's capacity quickly enough." El predictivo "scales out the MIG in advance of predicted load, so that new instances are ready to serve when the load arrives." — [Google Compute Engine docs, Predictive autoscaling](https://docs.cloud.google.com/compute/docs/autoscaler/predictive-autoscaling)
- **Google Cloud recomienda dejar margen (headroom) por el lag:** "Set your target utilization to reserve a buffer that can handle requests during a spike." y "That means your workload has a 30% CPU buffer for handling requests while new replicas are spinning up." También: "scale-ups might take some time due to infrastructure provisioning"; "Pause Pods are low-priority deployments that do nothing but reserve room in your cluster." — [Google Cloud Architecture Center, Best practices for running cost-optimized Kubernetes applications on GKE](https://docs.cloud.google.com/architecture/best-practices-for-running-cost-effective-kubernetes-applications-on-gke)

### Inferences
- Peor caso aproximado antes de que la nueva capacidad sirva tráfico, sumando parámetros por defecto documentados: hasta ~60 s de antigüedad de la métrica (scraping), hasta 15 s del bucle de control y el arranque del pod hasta Ready (≥ 30 s de retraso de readiness, más el arranque de la aplicación). Es decir, del orden de **1 a 2 minutos en una configuración por defecto**, más varios minutos si hace falta un nodo nuevo. Esta suma es **nuestra inferencia** a partir de los valores por defecto. No es una cifra publicada y no debe presentarse como tal.
- Que dos de los tres hiperescaladores (AWS y GCP) presenten productos predictivos con la motivación explícita de que lo reactivo llega tarde es la mejor validación externa de la premisa de Aegis.
- La propia guía de GKE de "dejar un 30 % de búfer de CPU" es una prescripción oficial de sobreaprovisionar para compensar el lag reactivo.

### Gaps
- No encontré en kubernetes.io una afirmación literal de que "HPA lags/reacts too late". El lag se deduce de la mecánica.
- La resolución de Metrics Server (la documentación del proyecto menciona por defecto `--metric-resolution=15s` en versiones recientes) no se verificó en esta sesión. El valor de 60 s procede del artículo de 2020 y puede estar desactualizado.
- No se obtuvo una cita oficial con "minutos" exactos para el aprovisionamiento de nodos por parte de Cluster Autoscaler (la guía de GKE no da la cifra).

## 2. Estudios revisados por pares que cuantifican el retraso del HPA o las violaciones de SLO bajo carga en picos

### Takeaway
Los estudios revisados por pares confirman cualitativamente que el HPA llega tarde y que las primeras subidas de escala concentran los fallos. Pero **no encontré una cifra revisada por pares, limpia y generalizable, del tipo "el HPA viola el SLO en X % durante los picos"**. Las cifras cuantificadas (15,3 % de violaciones de SLO, 53 % → 5 %) proceden de preprints de arXiv o de una tesis (fiabilidad C) y no sirven como titular.

### Cited Findings
- **Nguyen, Yeom, Kim, Park y Kim, "Horizontal Pod Autoscaling in Kubernetes for Elastic Container Orchestration", Sensors 20(16):4621, 2020 (MDPI, revisado por pares; fiabilidad A-/B+: revista de acceso abierto, banco de pruebas de 5 nodos con una aplicación limitada por CPU):**
  - Los fallos se concentran al empezar a escalar: "the first scaling-ups cause the majority of failed requests". Los pods nuevos todavía no están listos durante el pico de carga.
  - Con readiness probe no hubo fallos, pero "the general response time is significantly higher": el fallo se convierte en latencia.
  - La tercera subida de escala llegó tarde: en el segundo 110, 55 s después de la acción anterior, aunque la CPU seguía alta.
  - Con un clúster de 2 workers, "newly created pods take longer to get ready" y el tiempo de respuesta fue "remarkably longer".
  - Fuente: [PMC7471989 / doi:10.3390/s20164621](https://pmc.ncbi.nlm.nih.gov/articles/PMC7471989)
- **Rzadca et al., "Autopilot: Workload Autoscaling at Google Scale", EuroSys 2020 (ACM, revisado por pares, datos de producción de Google; fiabilidad A):** con autoscaling basado en ML e historial, la holgura (slack) baja al 23 % frente al 46 % de los trabajos gestionados a mano. Los trabajos gravemente afectados por OOM se reducen 10 veces. En el momento de la publicación, Autopilot gestionaba más del 48 % del uso de recursos de la flota. Trata de límites y réplicas y su reacción en producción, no de picos HTTP. Es evidencia fuerte sobre el **sobreaprovisionamiento manual** (pregunta 4), no sobre el lag del HPA. — [Google Research](https://research.google/pubs/autopilot-workload-autoscaling-at-google-scale/); [ACM DL doi:10.1145/3342195.3387524](https://dl.acm.org/doi/10.1145/3342195.3387524)
- **Toka, Dobreff, Fodor y Sonkoly, "Machine Learning-Based Scaling Management for Kubernetes Edge Clusters", IEEE Transactions on Network and Service Management, 2021 (revisado por pares, A):** el resumen afirma que su autoscaler predictivo "results in significantly fewer lost requests with just slightly more provisioned resources compared to the default baseline" (el HPA por defecto). La cifra exacta no se pudo verificar porque el texto completo está tras paywall. — [IEEE TNSM doi:10.1109/TNSM.2021.3052837 (resumen vía AMiner)](https://aminer.org/pub/605aa1b2e4510cd7c86a566c/machine-learning-based-scaling-management-for-kubernetes-edge-clusters)
- **Preprints o tesis (C, no usar como titular):**
  - SLO-Scaler: violaciones de SLO del 15,3 % con el HPA por defecto, frente al 11,8 % con KEDA y al 6,7 % con su método, bajo tráfico en ráfagas, con picos de p95 > 300 ms y unos 48 s de recuperación. — [arXiv 2608.18390](https://arxiv.org/pdf/2608.18390)
  - Tesis de Tampere: un pico de día de partido reproducido en k3s pasa de un 53 % de violaciones con el HPA reactivo a un 5 % con el predictivo. — [trepo.tuni.fi](https://trepo.tuni.fi/handle/10024/238698)
  - STaleX argumenta que el HPA por CPU no garantiza el SLO de tiempo de respuesta ante picos súbitos. — [arXiv 2501.18734](https://arxiv.org/pdf/2501.18734)
  - BASE (escalado adaptativo a ráfagas) reporta menos violaciones de SLO con 10 cargas reales. — [arXiv 2402.12962](https://arxiv.org/pdf/2402.12962.pdf)

### Inferences
- La afirmación más defendible con fuentes A es cualitativa y mecanística: "el HPA reacciona a métricas pasadas, en ciclos de 15 s, y los pods nuevos tardan en estar listos; las primeras subidas de escala concentran las peticiones fallidas" (Nguyen et al. 2020 más la documentación de Kubernetes).
- Las cifras de "% de violación de SLO del HPA" varían enormemente según el banco de pruebas (del 15 % al 53 %). Esa dispersión ya indica que no existe una cifra universal, y presentar una como tal sería engañoso.

### Gaps
- No se verificó (por falta de presupuesto de búsqueda o por paywall): Lorido-Botran et al., J. Grid Computing 2014 (encuesta seminal anterior a 2018); Qu, Calheiros y Buyya, ACM CSUR 2018 (encuesta sobre autoscaling de aplicaciones web). Ambas describen el problema conceptualmente, y no recuerdo cifras únicas que se puedan citar sin verificarlas.
- No encontré un artículo revisado por pares, de IEEE/ACM, específico sobre "flash crowds + HPA" con cifras de peticiones fallidas.
- La cifra numérica de peticiones perdidas de Toka et al. 2021 no se pudo extraer.

## 3. Con qué frecuencia ocurren las caídas por capacidad, picos de tráfico o problemas de TI/software

### Takeaway
Uptime Institute (B, la referencia del sector) muestra que las caídas de TI y de red son una parte relevante y creciente (23 % de las caídas con impacto en 2024), pero **no aísla "picos de tráfico" o "capacidad" como causa**. No hay un dato fiable que diga "X % de las caídas se deben a picos de tráfico".

### Cited Findings
- "Outages from IT and networking issues increased in 2024, totaling 23% of impactful outages." — [Uptime Institute, nota de prensa del Annual Outage Analysis 2025 (mayo de 2025)](https://uptimeinstitute.com/about-ui/press-releases/uptime-announces-annual-outage-analysis-report-2025)
- "Power remains the leading cause of impactful outages"; la frecuencia y la gravedad de las caídas descienden "for the fourth consecutive year". — [Uptime Institute 2025](https://uptimeinstitute.com/about-ui/press-releases/uptime-announces-annual-outage-analysis-report-2025)
- El 53 % de los operadores declaró una caída en los últimos tres años (78 % en 2020). Solo el 9 % de los incidentes de 2024 se clasificó como grave o severo. Los proveedores externos de TI y de centros de datos (nube, telecomunicaciones, colocation) suman unos dos tercios de las caídas públicas registradas en nueve años. — [Data Center Knowledge](https://www.datacenterknowledge.com/outages/data-center-outages-decline-for-fourth-straight-year-but-issues-persist); [Computer Weekly](https://www.computerweekly.com/news/366623669/Datacentre-outages-decreasing-in-frequency-Uptime-Institute-Intelligence-data-shows) (fuentes secundarias que resumen el informe; el informe completo es de pago)
- "Nearly 40% of organizations have suffered a major outage caused by human error over the past three years." — [Uptime Institute 2025](https://uptimeinstitute.com/about-ui/press-releases/uptime-announces-annual-outage-analysis-report-2025)

### Inferences
- Uptime trata sobre todo de centros de datos e infraestructura. Usarlo para "los picos de tráfico tumban servicios" sería forzar la fuente. Como mucho sirve de contexto: las caídas de TI y de red son relevantes (23 %) y crecen.

### Gaps
- No se encontró un desglose fiable de "capacidad o picos de tráfico" como causa raíz en Uptime (el informe completo es de pago) ni en otros informes.
- No se revisaron postmortems públicos de proveedores de nube atribuidos a picos de tráfico (por presupuesto). Si se usan, serán anécdotas, no estadísticas.
- Uptime no publica en la nota de prensa los tamaños de muestra de su encuesta 2025.

## 4. Evidencia de que las organizaciones sobreaprovisionan para compensar (baja utilización en Kubernetes)

### Takeaway
La evidencia de sobreaprovisionamiento es abundante y numérica. La más fiable es la de Google Autopilot (revisada por pares: 46 % de holgura con gestión manual). Las cifras de proveedores (CAST AI: 10 % de utilización media de CPU; Datadog: 83 % del coste de contenedores ociosos) tienen muestras grandes pero sesgo comercial.

### Cited Findings
- **Google Autopilot (A, EuroSys 2020):** los trabajos gestionados a mano tienen un 46 % de holgura (límite menos uso), frente al 23 % con Autopilot. — [Google Research](https://research.google/pubs/autopilot-workload-autoscaling-at-google-scale/)
- **CAST AI 2025 Kubernetes Cost Benchmark (C, proveedor; más de 2.100 organizaciones; AWS, GCP y Azure; enero-diciembre de 2024; publicado el 5 de marzo de 2025):** "average CPU utilization across Kubernetes clusters remains low at just 10%, down from 13% last year. Memory utilization is 23%". — [Nota de prensa de CAST AI](https://cast.ai/press-release/new-kubernetes-cost-benchmark-report-reveals-persistent-cloud-waste/); [página del informe](https://cast.ai/kubernetes-cost-benchmark/)
- **CAST AI, informe posterior (C, sin verificar de primera mano):** CPU al 8 % y memoria al 20 % en 2025; sobreaprovisionamiento de CPU del 40 % → 69 %. Algunas fuentes secundarias lo citan como informe de 2026 con más de 23.000 clústeres. La etiqueta del año y la muestra son confusas. — [CAST AI, Kubernetes optimization report](https://cast.ai/reports/kubernetes-optimization-report/)
- **Datadog State of Cloud Costs 2024 (C/B, proveedor de observabilidad; "hundreds of organizations" en AWS; datos de mayo de 2023 a abril de 2024):** "Our research shows that 83 percent of container costs are associated with idle resources." y "About 54 percent of this wasted spend is on cluster idle, which is the cost of overprovisioning cluster infrastructure"; el resto es inactividad de cargas ("resource requests that are larger than their workloads require"). — [Datadog State of Cloud Costs](https://www.datadoghq.com/state-of-cloud-costs/)
- **Prescripción oficial de búfer:** Google Cloud recomienda fijar el objetivo del HPA dejando un búfer de CPU del 30 % mientras arrancan las réplicas, y usar pause pods para reservar espacio. — [Google Cloud, prácticas recomendadas de GKE](https://docs.cloud.google.com/architecture/best-practices-for-running-cost-effective-kubernetes-applications-on-gke)

### Inferences
- El vínculo causal "sobreaprovisionan *porque* lo reactivo llega tarde" solo lo afirman explícitamente fuentes oficiales (el búfer del 30 % de GKE y el "avoid the need to over provision" de AWS). CAST AI y Datadog miden el desperdicio, pero no atribuyen su causa al lag del autoscaler (influyen también la "ansiedad" de los desarrolladores, los requests mal dimensionados, etc.).

### Gaps
- No se verificaron Sysdig (Cloud-Native Security and Usage Report) ni las encuestas de la CNCF. El conocido dato de Sysdig 2023 sobre la CPU sobreasignada no se confirmó en esta sesión, así que no se incluye.
- El Datadog Container Report (dato de que la mayoría de los contenedores usa menos de la mitad de lo solicitado) no se verificó.

## 5. Qué cifra única es el titular más fiable y relevante, y por qué

### Takeaway
**No existe una cifra única, de fuente muy fiable, que mida "el autoscaling reactivo falla un X % en los picos".** La recomendación honesta es un titular de dos piezas: (a) una **cita oficial** de un hiperescalador que admite que lo reactivo llega tarde y (b) una **cifra cuantificada y revisada por pares del coste de compensarlo** (sobreaprovisionamiento).

### Cited Findings
- **Opción recomendada (A + A):**
  - Cita: "an autoscaler can only scale a group reactively, based on observed changes in load in real time … if your application takes a few minutes or more to initialize, adding instances in response to real-time changes might not increase your application's capacity quickly enough." — [Google Cloud docs](https://docs.cloud.google.com/compute/docs/autoscaler/predictive-autoscaling). Alternativa equivalente: "dynamic scaling, which is reactive in nature" — [AWS docs](https://docs.aws.amazon.com/autoscaling/ec2/userguide/ec2-auto-scaling-predictive-scaling.html)
  - Cifra de apoyo: los trabajos gestionados a mano en Google dejan un **46 % de holgura** de recursos (Autopilot, EuroSys 2020). — [Google Research](https://research.google/pubs/autopilot-workload-autoscaling-at-google-scale/)
- **Si la diapositiva necesita una cifra de daño en picos:** usar Nguyen et al. 2020 (revisado por pares), "the first scaling-ups cause the majority of failed requests". — [PMC7471989](https://pmc.ncbi.nlm.nih.gov/articles/PMC7471989). Es cualitativo ("majority"), pero procede de un experimento revisado por pares con el HPA real.
- **Cifra llamativa pero de menor fiabilidad:** "Kubernetes clusters average 10% CPU utilization" (CAST AI 2025, más de 2.100 organizaciones). Hay que marcarla como dato de proveedor. — [CAST AI](https://cast.ai/press-release/new-kubernetes-cost-benchmark-report-reveals-persistent-cloud-waste/)

### Inferences
- Por qué esta combinación: las citas de AWS y Google son de máxima autoridad, verificables y siguen vigentes, y afirman exactamente la premisa de Aegis (escalar antes de que llegue la carga). Autopilot es revisado por pares, con datos de producción a escala de Google, y cuantifica el coste de la alternativa manual o sobreaprovisionada. Ninguna depende de las cifras de laboratorio del equipo.
- Hay que evitar en el titular el 15,3 % o el 53 % de violaciones de SLO del HPA: son preprints o una tesis, con bancos de pruebas no comparables.

### Gaps
- Un estudio revisado por pares y de amplia muestra que mida el porcentaje de peticiones fallidas o de violaciones de SLO del HPA por defecto ante picos reales cerraría el hueco. No lo encontré en esta sesión. Candidatos a revisar en el texto completo: Toka et al. IEEE TNSM 2021; el HPA consciente del tráfico de IEEE Access 2022 ("Traffic-aware horizontal pod autoscaler", Phuc et al., [DOAJ](https://doaj.org/article/393f77ac3b744e5c80bd5fa51b3a00b4)); Qu, Calheiros y Buyya, CSUR 2018.
