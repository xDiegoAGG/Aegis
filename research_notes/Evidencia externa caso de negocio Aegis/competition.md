# Competitive landscape: keeping Kubernetes workloads ahead of traffic spikes (vs. Aegis)

Research date: 2026-11-05. Facts marked **[fetched]** were read on the source page in this session. Facts marked **[prior knowledge, unverified 2026]** come from the researcher's background knowledge of official docs and were NOT re-read in this session. Check them before putting them on a slide. Vendor statements are marked **[vendor claim]**.

Aegis reference profile (from the brief, not externally verified): proactive pod autoscaler. Every 5 s it reads RPS from Prometheus, projects demand T+lag (about 30 s) with a linear trend, and computes P(capacity < demand). When that risk is above 70% it raises the HPA's minReplicas. Scale-down waits 15 to 60 s depending on risk. Decisions are explained in plain words. It needs no ML and no history beyond 30 s. It plugs into the existing HPA. Open source, single namespace, one Deployment. Weak spots: it cannot anticipate an instant step spike (it then reacts within one 5 s cycle), and it needs per-pod capacity calibration.

---

## Q1. Signal, anticipation horizon, history needs, and scope (pods/nodes/VMs) of each competitor

### Takeaway
Every widely adopted pod-level autoscaler (HPA, KEDA, Knative KPA) is **reactive**: it scales after a metric crosses a target. The products that do **predict** either forecast daily or weekly seasonality from days to weeks of history and act on VMs (AWS, GCP), or depend on an external ML SaaS that needs 7 to 14 days of history (PredictKube). None of the open-source pod autoscalers found predicts on a seconds-scale horizon tied to pod readiness time.

### Cited Findings

**Kubernetes HPA (default)**
- Control loop runs every 15 s by default (`--horizontal-pod-autoscaler-sync-period`). It acts on objects with a scale subresource (Deployments, StatefulSets). It supports resource metrics (`metrics.k8s.io`), custom metrics and external metrics. **[fetched]** — [Kubernetes HPA docs, 2026](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/)
- Defaults: global tolerance 10%; scale-down stabilization window 300 s; scale-up with no stabilization and up to 4 pods or 100% per 15 s; not-ready pods are treated conservatively during scale-up; `--horizontal-pod-autoscaler-initial-readiness-delay` 30 s, CPU initialization period 5 min. **[prior knowledge, unverified 2026: the fetched page was truncated before these sections]** — [Kubernetes HPA docs](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/)
- It is reactive by design. The desired replica count is computed from the current metric value against the target, with no forecasting. **[fetched, implied by the algorithm description]** — [Kubernetes HPA docs](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/)

**Kubernetes HPA (tuned)**
- Per-HPA configurable tolerance (KEP-4951): alpha in v1.33, beta in v1.35, and stable targeted for v1.37 (feature gate `HPAConfigurableTolerance`). — [KEP-4951](https://www.kubernetes.dev/resources/keps/4951/); [K8s blog v1.33, 2025](https://kubernetes.io/blog/2025/04/28/kubernetes-v1-33-hpa-configurable-tolerance/). GA in 1.37 is reported by [PerfectScale, 2026](https://www.perfectscale.io/blog/kubernetes-v1-37-whats-new), a third-party preview article that was not checked against the official release notes.
- Tuning options (`behavior` policies, a lower target, custom RPS metric through prometheus-adapter) make the HPA faster or give it more headroom. It stays reactive, and the extra headroom is paid for all the time. (Inference, see below.)

**KEDA (Prometheus scaler)**
- KEDA graduated from CNCF in Aug 2023. — [CNCF news, 2023](https://www.cncf.io/news/2023/08/22/itops-times-keda-graduates-from-cncf/)
- KEDA drives an HPA under the hood. Each trigger feeds a metric, and the HPA takes the maximum across metrics. — [KEDA cron scaler docs v2.18](https://keda.sh/docs/2.18/scalers/cron/) **[fetched]**
- With a Prometheus RPS query as the trigger, KEDA scales on the same signal Aegis uses, but reactively: metric/threshold → HPA. It adds scale-to-zero (`minReplicaCount: 0`, activation threshold). (Design inference from the docs.)

**KEDA (cron scaler)**
- Scales to `desiredReplicas` between a `start` and an `end` cron expression and returns to `minReplicaCount` outside the window. Scale-down after `end` waits for `cooldownPeriod` (default 5 min). Combined with other triggers, it acts as a "dynamic minimum" during the window. **[fetched]** — [KEDA cron scaler docs v2.18](https://keda.sh/docs/2.18/scalers/cron/)
- It is proactive only for **known, scheduled** peaks. The operator has to know the schedule in advance.

**KEDA HTTP add-on**
- Status: **beta**, "v1.0 release planned", and minor breaking changes may occur before v1.0. Apache-2.0, about 558 GitHub stars. It scales HTTP workloads based on incoming traffic, including to and from zero. The repo has interceptor, operator and scaler components. It points to Kedify's HTTP Scaler as the commercially supported alternative. **[fetched]** — [github.com/kedacore/http-add-on, 2026](https://github.com/kedacore/http-add-on)
- It uses an interceptor proxy in the request path that counts pending/in-flight requests. **[prior knowledge, unverified 2026]**. This adds a data-plane hop, which Aegis does not need.

**Knative Pod Autoscaler (KPA)**
- Metrics are `concurrency` or `rps`. Stable window default 60 s (range 6 s to 1 h). Panic window default 10% of the stable window (so 6 s). Panic threshold default 200%: "panic mode will be started if traffic is twice as high as the current replica population can handle." In panic mode it does not scale down. Scale to zero happens after no traffic for the whole stable window. **[fetched]** — [Knative KPA docs, 2026](https://knative.dev/docs/serving/autoscaling/kpa-specific/)
- Knative has graduated from CNCF. The TOC due-diligence document says the graduation criteria were completed, but the exact date was not confirmed in this session. — [CNCF TOC Knative graduation DD](https://gitea.cncfstack.com/cncf/toc/src/commit/ff199a9c61d0386431c1aa1d31f98331cb4def7b/projects/knative/knative-graduation-dd.md) (mirror); [CNCF projects page](https://www.cncf.io/projects-graduated/)
- The KPA replaces the HPA for Knative Services, and Knative Serving is required (queue-proxy sidecar, Activator). **[prior knowledge, unverified 2026]**

**PredictKube (Dysnix, KEDA scaler)**
- "AI-based predictive scaling based on Prometheus metrics & PredictKube SaaS". It needs an API key from Dysnix, and the "AI model ... requires API to connect to the project". Data leaves the cluster for an external SaaS. Recommended history (`historyTimeWindow`) is **7 to 14 days**. `predictHorizon` example is "2h", "usually equal to your application's cooldown period". Available since KEDA v2.6, maintained by Dysnix, and the docs carry no deprecation notice. **[fetched]** — [KEDA PredictKube scaler docs v2.18](https://keda.sh/docs/2.18/scalers/predictkube/)
- PredictKube pricing and current adoption were not found (see Gaps).

**Kubernetes VPA**
- Adjusts CPU and memory **requests** per pod (vertical scaling), not the replica count. Do not use it together with an HPA on the same CPU or memory metric. It is complementary to Aegis, not a competitor on spikes. In-place pod resize (KEP-1287) reached beta in 1.33. **[prior knowledge, unverified 2026]** — [VPA repo](https://github.com/kubernetes/autoscaler/tree/master/vertical-pod-autoscaler)

**AWS EC2 Auto Scaling predictive scaling** (acts on **EC2 instances / ASGs**, not pods)
- Needs at least 24 h of metric data to start forecasting and analyses up to 14 days. It produces an **hourly** forecast for the next 48 h, updated every 6 h. It starts in "forecast only" mode. Its forecast **never scales in**, so dynamic policies are needed for that. It scales at the start of each hour unless `SchedulingBufferTime` pre-launches instances. Forecasts are "more effective if historical data spans two full weeks". A new ASG restarts the 24 h wait. It assumes a homogeneous group. **[fetched]** — [AWS docs: How predictive scaling works, 2026](https://docs.aws.amazon.com/autoscaling/ec2/userguide/predictive-scaling-policy-overview.html)
- Good fit: "cyclical traffic", "recurring on-and-off workload patterns", "applications that take a long time to initialize". **[fetched]** — [AWS docs: Predictive scaling, 2026](https://docs.aws.amazon.com/autoscaling/ec2/userguide/ec2-auto-scaling-predictive-scaling.html)

**Google Cloud predictive autoscaling (Managed Instance Groups, VMs)**
- **CPU utilization only**. Load balancing and Cloud Monitoring metrics are not supported. It needs **3 days** of CPU-autoscaling history and uses up to 3 weeks. Forecasts are recomputed every few minutes. It predicts daily and weekly patterns only, not one-time events or patterns shorter than 10 minutes. Sudden unpredictable spikes are handled reactively. A new or blue-green MIG needs another 3 days of history. It "may raise costs" because instances start earlier. It uses the initialization period to decide how far ahead to scale. **[fetched]** — [Google Cloud docs: Predictive autoscaling, 2026](https://docs.cloud.google.com/compute/docs/autoscaler/predictive-autoscaling)

**Karpenter / Cluster Autoscaler (node level, complementary)**
- Karpenter provisions nodes in response to **unschedulable (pending) pods**. It was originally built by AWS, with a provider-agnostic core (`kubernetes-sigs/karpenter`) and provider-specific implementations. — [third-party guide, 2026](https://www.skills.lc/tylertitsworth/skills/tylertitsworth-skills-karpenter-skill-md) (low-quality source); [kubernetes-sigs/karpenter](https://www.github.com/kubernetes-sigs/karpenter/issues)
- Cluster Autoscaler likewise adds nodes when pods are pending and removes underused nodes. Both are reactive to pod scheduling and do not decide replica counts. **[prior knowledge, unverified 2026]** — [kubernetes/autoscaler](https://github.com/kubernetes/autoscaler)
- Karpenter's CNCF status was not confirmed. It is a Kubernetes SIG Autoscaling subproject (kubernetes-sigs), not a separate CNCF project. **[prior knowledge]**

**Commercial products**
- **Datadog Kubernetes Autoscaling:** multidimensional (replicas plus container size), driven by a `DatadogPodAutoscaler` CRD with the Datadog Cluster Agent as controller. Live workload scaling needs Agent 7.66.1+, and the docs advise **removing existing HPAs/VPAs** before enabling it, so it replaces the HPA. Datadog says it runs this on about 30,000 of its own deployments **[vendor claim]**. — [Datadog docs](https://docs.datadoghq.com/containers/autoscaling); [Datadog blog](https://www.datadoghq.com/blog/how-we-saved-with-kubernetes-autoscaling). No GA date or exact pricing was confirmed. It requires a Datadog subscription.
- **StormForge Optimize Live (now part of CloudBolt):** ML rightsizing of requests and limits plus the **HPA target utilization**. It is "HPA-compatible", with a 7-day initial learning period. The agent runs in the cluster, while the ML control plane is SaaS. "50% or more" cost reduction **[vendor claim]**. It is about efficiency and rightsizing, not spike anticipation. — [CloudBolt Optimize Live](https://www.cloudbolt.io/stormforge-by-cloudbolt/optimize-live/); [StormForge v2 press release](https://stormforge.io/press-releases/stormforge-launches-v2-optimize-live-kubernetes-resource-optimization)
- **CAST AI:** the marketing says its "predictive model [is] trained on data from thousands of clusters" **[vendor claim]**. The legacy (v1, deprecated) horizontal scaling docs show reactive scaling on short-term CPU (about the last 3 min). — [CAST AI legacy HPA v1 docs](https://docs.cast.ai/docs/workload-autoscaler-legacy-hpa-v1). An AWS Marketplace user review says it does not anticipate sudden nonlinear spikes (single anecdote) — [AWS Marketplace reviews](https://aws.amazon.com/marketplace/reviews/reviews-list/prodview-vtvxyzbzs3huy?page=6). Pricing is quote-based. Third-party figures conflict ($200/mo + $7.50/CPU vs $1000/mo + $5/vCPU) and are unverified — [PricingSaaS](https://pricingsaas.com/companies/cast)
- **Spot Ocean (NetApp → Flexera, acquisition completed Mar 2025):** node-level, container-driven infrastructure autoscaler. It keeps **headroom** (spare vCPU, memory and GPU as a percentage of cluster usage, automatic or manual) so pending pods schedule instantly. It also predicts spot interruptions. It does not decide pod replica counts. — [Flexera: Ocean headroom](https://www.flexera.com/blog/finops/ocean-explained-headroom/); [Flexera acquisition press release, 2025](https://www.flexera.com/about-us/press-center/flexera-completes-acquisition-of-netapps-spot-finops-portfolio-de)
- **GKE Autopilot:** a managed GKE mode where Google manages nodes and billing is per pod resource request. Pod replica scaling still uses the HPA (or VPA/MPA) that the user configures. It is complementary infrastructure and offers no predictive pod scaling. **[prior knowledge, unverified 2026]** — [GKE Autopilot overview](https://cloud.google.com/kubernetes-engine/docs/concepts/autopilot-overview)

**Research proactive autoscalers**
- Peer-reviewed taxonomy: Qu, Calheiros & Buyya, "Auto-scaling Web Applications in Clouds: A Taxonomy and Survey", ACM Computing Surveys 51(4), 2018, DOI 10.1145/3148149. It classifies auto-scalers as reactive vs proactive (forecast-based). — [arXiv 1609.09224](https://arxiv.org/abs/1609.09224); [Western Sydney record](https://researchers.westernsydney.edu.au/en/publications/auto-scaling-web-applications-in-clouds-a-taxonomy-and-survey/)
- Xu, Liao, Wen, Wu, Ye, Buyya, Xu, "Auto-scaling Approaches for Microservice Applications: A Survey and Taxonomy", arXiv 2507.17128 (2025, rev. Mar 2026, **preprint, no venue listed**). Its taxonomy covers infrastructure, architecture, scaling methods, objectives and behavior modeling. Open challenges include workload characterization and anomaly detection. — [arXiv 2507.17128](https://arxiv.org/abs/2507.17128)
- "Kubernetes Autoscaling: A Comprehensive Review on Machine Learning Techniques" (Preprints.org, Jun 2026, **not peer-reviewed**) concludes that time-series forecasting is the most mature approach for proactive HPA. — [Preprints.org 202606.1094](https://www.preprints.org/manuscript/202606.1094/v1)
- Typical research prototypes forecast about 1 minute ahead with Transformer or Informer models trained on traces (e.g., Alibaba), or use ARIMA. A Tampere thesis notes that scrape interval + HPA cycle + 60 to 120 s cold start can add up to 3 to 5 min before new capacity is available. — [Tampere University thesis](https://trepo.tuni.fi/handle/10024/238698); [Theseus ARIMA thesis, 2026](https://www.theseus.fi/handle/10024/918185). Low-confidence aggregator pages that describe InformerAutoScale and CATScaler were found but not verified: [atlante.unipv.it](https://atlante.unipv.it/predictive-autoscaler-kubernetes)

### Inferences
- The field splits along two axes. On **horizon and history**: seconds/none (HPA, KEDA, KPA, Aegis), hours/days (PredictKube 7 to 14 days, AWS 24 h to 14 days, GCP 3 days to 3 weeks), and schedule (KEDA cron). On **layer**: pods (HPA, KEDA, KPA, PredictKube, Datadog, Aegis), sizes (VPA, StormForge), nodes (Karpenter, CA, Ocean, Autopilot) and VMs (AWS, GCP).
- Aegis occupies a sparsely populated cell: **pod level, proactive, seconds-scale horizon matched to pod readiness, no training history**.

### Gaps
- PredictKube pricing, adoption, and whether Dysnix still operates the SaaS in 2026 were not found.
- Datadog Kubernetes Autoscaling pricing and GA date were not confirmed.
- No independent benchmark compares these tools on spike response. All performance numbers found are vendor claims or theses.

---

## Q2. Does it explain its decisions to operators?

### Takeaway
No tool reviewed offers per-decision natural-language explanations the way Aegis does. The open-source tools expose events, conditions and metrics. The commercial tools show recommendations and dashboards.

### Cited Findings
- AWS predictive scaling exposes the forecast (GetPredictiveScalingForecast, console graphs), runs in forecast-only mode first, and gives "recommendations based on observations about potential policy performance". This is forecast transparency, not a reason given for each decision. — [AWS docs, 2026](https://docs.aws.amazon.com/autoscaling/ec2/userguide/predictive-scaling-policy-overview.html)
- StormForge lets you review recommendations manually during its 7-day learning period. — [CloudBolt Optimize Live](https://www.cloudbolt.io/stormforge-by-cloudbolt/optimize-live/)
- Spot Ocean dashboards show headroom composition by node, VNG and cluster. — [Flexera blog](https://www.flexera.com/blog/finops/ocean-explained-headroom/)
- HPA, KEDA and KPA report status through Kubernetes conditions and events (e.g., `ScalingActive`, `AbleToScale`). **[prior knowledge, unverified 2026]**
- The research search found no paper combining explainability with proactive Kubernetes scaling. — search results summarized above ([atlante.unipv.it](https://atlante.unipv.it/predictive-autoscaler-kubernetes), [theseus.fi](https://www.theseus.fi/handle/10024/918185))

### Inferences
- "Every decision explained in plain words" is a real differentiator. It is a UX and trust feature, not a performance one, and it can be copied. Present it as secondary to the risk-based mechanism.

### Gaps
- The Datadog and CAST AI UIs may contain explanation features that were not reviewed.

---

## Q3. Maturity: CNCF status, adoption, license, pricing

### Takeaway
Aegis competes against graduated CNCF projects and well-funded vendors. On maturity it is the weakest entry, so it should be positioned as an add-on to them, not a replacement.

### Cited Findings
| Tool | Status / license / price | Source |
|---|---|---|
| Kubernetes HPA | Core Kubernetes, Apache-2.0, free | [kubernetes.io](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/) |
| KEDA | CNCF **graduated** (Aug 2023), Apache-2.0, free | [CNCF news 2023](https://www.cncf.io/news/2023/08/22/itops-times-keda-graduates-from-cncf/) |
| KEDA HTTP add-on | **Beta**, Apache-2.0, about 558 stars | [GitHub](https://github.com/kedacore/http-add-on) |
| Knative (KPA) | CNCF **graduated** (date not confirmed; incubating since 2022) | [CNCF TOC DD](https://gitea.cncfstack.com/cncf/toc/src/commit/ff199a9c61d0386431c1aa1d31f98331cb4def7b/projects/knative/knative-graduation-dd.md) |
| PredictKube | KEDA scaler since v2.6, needs Dysnix SaaS API key; pricing not found | [KEDA docs](https://keda.sh/docs/2.18/scalers/predictkube/) |
| AWS / GCP predictive | Managed features. No separate fee was found in this session; you pay for instances, and GCP warns of possibly higher cost | [AWS](https://docs.aws.amazon.com/autoscaling/ec2/userguide/predictive-scaling-policy-overview.html), [GCP](https://docs.cloud.google.com/compute/docs/autoscaler/predictive-autoscaling) |
| Karpenter / CA | kubernetes-sigs subprojects, Apache-2.0 **[prior knowledge]** | [GitHub](https://github.com/kubernetes/autoscaler) |
| StormForge | Commercial (CloudBolt), SaaS + agent | [CloudBolt](https://www.cloudbolt.io/stormforge-by-cloudbolt/optimize-live/) |
| CAST AI | Commercial, free monitoring tier, quote-based; third-party prices conflict | [PricingSaaS](https://pricingsaas.com/companies/cast) |
| Spot Ocean | Commercial, Flexera since 2025 | [Flexera](https://www.flexera.com/about-us/press-center/flexera-completes-acquisition-of-netapps-spot-finops-portfolio-de) |
| Datadog K8s Autoscaling | Commercial, requires Datadog agent 7.66.1+ | [Datadog docs](https://docs.datadoghq.com/containers/autoscaling) |

### Gaps
- KEDA star count and adoption figures (e.g., CNCF survey percentages) were not retrieved in this session.

---

## Q4. Documented limitations, and where Aegis genuinely fits (honest positioning)

### Takeaway
Aegis's real differentiation is narrow and defensible: **proactive on a seconds-scale horizon equal to pod readiness, from RPS, with zero training history, expressed as a risk probability, and layered on the unchanged HPA**. It does not differentiate on signal (KEDA and KPA already scale on RPS and concurrency), on step spikes (nobody predicts them, Aegis included), or on maturity.

### Cited Findings (limitations of competitors)
- HPA: 15 s loop, metric-threshold driven, 300 s default scale-down stabilization **[partly prior knowledge]**. — [K8s docs](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/)
- KEDA: drives the HPA and takes the maximum across triggers. The cron scaler only covers known windows, with a 5 min default cooldown. — [KEDA cron docs](https://keda.sh/docs/2.18/scalers/cron/)
- KEDA HTTP add-on: beta, with breaking changes possible before v1.0. — [GitHub](https://github.com/kedacore/http-add-on)
- Knative KPA: panics only when traffic reaches about 2x what current pods can handle (default 200%), over a 6 s window (10% of 60 s). It requires Knative Serving. — [Knative docs](https://knative.dev/docs/serving/autoscaling/kpa-specific/)
- PredictKube: 7 to 14 days of history, external SaaS and API key, hour-scale horizon. — [KEDA docs](https://keda.sh/docs/2.18/scalers/predictkube/)
- AWS predictive: 24 h minimum and 14 days ideal, hourly granularity, 48 h horizon, never scales in, assumes a homogeneous group, VMs only. — [AWS docs](https://docs.aws.amazon.com/autoscaling/ec2/userguide/predictive-scaling-policy-overview.html)
- GCP predictive: CPU only, 3 days of history, daily/weekly patterns only, nothing shorter than 10 min, unpredictable spikes handled reactively. — [GCP docs](https://docs.cloud.google.com/compute/docs/autoscaler/predictive-autoscaling)
- Datadog: replaces the HPA (remove existing HPAs/VPAs). — [Datadog docs](https://docs.datadoghq.com/containers/autoscaling)
- CAST AI legacy horizontal scaling: reactive on about 3 min of CPU. — [CAST AI docs](https://docs.cast.ai/docs/workload-autoscaler-legacy-hpa-v1)

### Inferences (positioning, for the slide)
- **Genuinely differentiated:**
  1. *Horizon matched to pod readiness (about 30 s), with no history.* Cloud predictive tools need 1 to 21 days of history and forecast daily or weekly cycles at hourly or 10-minute granularity. They cannot see a ramp that started 20 s ago. GCP says this explicitly about sub-10-minute patterns.
  2. *Risk-based decision* (probability that capacity falls short) instead of a fixed utilization target. No reviewed tool expresses its decision as a shortfall probability.
  3. *Plugs into the existing HPA by raising minReplicas.* The HPA stays as the safety net. Datadog requires removing the HPA, and KPA requires Knative.
  4. *Plain-language explanation for every decision.* Not found elsewhere.
  5. *No external SaaS and no data leaving the cluster,* unlike PredictKube, StormForge's ML plane, CAST AI and Datadog.
- **Not differentiated (be honest):**
  - *Signal.* KEDA's Prometheus scaler on RPS and Knative's rps/concurrency already scale on request rate. Aegis's gain over a well-tuned KEDA-on-RPS comes only from the trend projection during **ramps**, which is worth roughly one pod-readiness interval of lead time.
  - *Instant spikes.* Aegis cannot predict a step. It reacts within one 5 s cycle, comparable to KPA panic mode (6 s window) and faster than the default HPA (15 s loop plus metric pipeline delay). Claim parity here, not superiority.
  - *Scheduled peaks.* KEDA cron and AWS/GCP predictive handle known daily or weekly peaks well, often with more lead time than Aegis's 30 s.
  - *Maturity and scale.* Aegis is single-namespace and new. HPA, KEDA and Knative are core or graduated CNCF projects.
  - *Calibration.* Aegis needs measured per-pod capacity. KPA also needs a target concurrency per pod, so this weakness is shared, but HPA on CPU needs no such step.
- **Complementary, not competitors:** Karpenter, Cluster Autoscaler, Spot Ocean headroom and GKE Autopilot (nodes); VPA and StormForge (pod sizes). Aegis's 30 s lead only helps if a node is available. Pending pods on a cold node add the node provisioning time, so Aegis plus node headroom (Ocean or over-provisioning) is the natural pairing.
- **Suggested one-line slide answer:** "Your competition is the reactive HPA/KEDA you already run, and the cloud predictive scalers that need weeks of history and only see daily cycles. Aegis is the only open-source layer that looks one pod-startup ahead on live request rate, says why, and leaves your HPA in place."

### Gaps
- No public head-to-head benchmark of Aegis vs KEDA-on-RPS vs KPA on identical ramps. Only Aegis's own campaign data (repo `docs/`) would support a quantitative claim.
- Whether newer research (2025–2026) includes a short-horizon, risk-based, explainable scaler could not be ruled out with the searches done. The claim "no one else does this" should be worded as "none found among mainstream tools".
