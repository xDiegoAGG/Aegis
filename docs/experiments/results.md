# Results of the experiment design

[Español](results.es.md) · Campaign of 2026-11-05: **54 runs** (3 autoscalers × 3 loads × 6 blocks), run in the random order registered in [design.md](design.md) before the first run. No run was discarded or repeated. Raw data: `docs/tests/<load>-<autoscaler>/data/`; generated analysis: [design-results.md](../tests/design-results.md); deviations: [design.md, section 10](design.md#deviation-log).

## 1. In one paragraph

Against the same loads, **Aegis had fewer failed requests than both HPAs in 5 of the 6 pre-registered contrasts**: on the ramp 1.9% against 16.9% (default HPA) and 15.4% (tuned HPA), on the spike 5.6% against 26.7% and 24.9%, and on the waves 1.4% against 7.1% (tuned HPA). The exception is the waves against the default HPA (1.4% vs 3.7%, not significant): that HPA keeps its pods for 300 s, which helps between waves and costs 37% more pod-minutes. Aegis was degraded half the time or less on the ramp and the spike and asked for the 2nd pod 1–2 minutes earlier. **H2 is refuted**: the advantage on the spike, where there is no trend to anticipate, is at least as large as on the ramp. The gain does not only come from anticipating; Aegis reacts every 5 s to the request rate, while the HPA reacts to averaged CPU. **H3 is refuted as well**: with the 15–60 s scale-down rule, Aegis used the same or fewer pod-minutes than the HPAs, except on the spike against the tuned HPA.

## 2. Primary metric: failed requests (%)

Mean of 6 blocks ± standard deviation [min–max].

| Load | Aegis | Default HPA | Tuned HPA |
|---|---|---|---|
| Ramp | **1.9 ± 2.3** [0.0–5.4] | 16.9 ± 9.2 [9.8–34.5] | 15.4 ± 9.6 [4.1–32.6] |
| Spike | **5.6 ± 1.1** [4.5–7.7] | 26.7 ± 15.7 [17.4–58.2] | 24.9 ± 4.6 [21.1–34.0] |
| Waves | **1.4 ± 1.8** [0.0–4.4] | 3.7 ± 3.2 [0.0–8.3] | 7.1 ± 2.6 [3.9–11.7] |

### Pre-registered contrasts (H1)

Randomized block ANOVA per load; Holm over the 6 contrasts; decided on ranks where the residuals are not normal (the spike, Shapiro-Wilk p = 0.015), as the plan fixes.

| Load | Contrast | Difference [95% CI] | p Holm | Decided on | Cliff's δ | **H1** |
|---|---|---|---|---|---|---|
| Ramp | Aegis − default HPA | −15.0 [−25.3, −4.8] | 0.026 | ANOVA | −1.00 | **Supported** |
| Ramp | Aegis − tuned HPA | −13.6 [−23.8, −3.3] | 0.030 | ANOVA | −0.94 | **Supported** |
| Spike | Aegis − default HPA | −21.0 [−31.4, −10.6] | 0.001 | ranks | −1.00 | **Supported** |
| Spike | Aegis − tuned HPA | −19.2 [−29.6, −8.8] | 0.0001 | ranks | −1.00 | **Supported** |
| Waves | Aegis − default HPA | −2.3 [−5.7, +1.2] | 0.18 | ANOVA | −0.39 | Not shown |
| Waves | Aegis − tuned HPA | −5.6 [−9.1, −2.2] | 0.019 | ANOVA | −0.94 | **Supported** |

Cliff's δ = −1 means every Aegis run failed less than every run of that HPA.

### Sensitivity (post hoc, not in the registered plan)

Aegis runs vary far less than HPA runs, so the equal-variance assumption of the ANOVA does not hold well. Two analyses that do not need it:

- **Paired t by block on log(1 + %)**: the same 5 contrasts are significant after Holm.
- **Paired t by block on the raw %** (the most conservative, 5 degrees of freedom): 2 significant (ramp vs default HPA, spike vs tuned HPA), 3 at p = 0.063.

The direction is the same in every analysis. The honest summary: **5 of 6 contrasts significant under the registered analysis and on the log scale; under the most conservative analysis, 2 significant and 3 borderline.**

## 3. H2: does the benefit need a trend?

(Aegis − default HPA on the ramp) − (Aegis − default HPA on the spike), paired by block: **+6.0 points [−4.3, +16.2], p = 0.20**. The registered rule (interval below 0) is not met; the point estimate even goes the other way. **H2 is not supported.**

Why: on the spike Aegis asked for the 2nd pod at 45 s (the HPAs at 103–127 s), 12 s after the traffic passed one pod. It reacted, it did not anticipate, but it reacted on the signal that matters (requests per second, every 5 s) instead of CPU averaged by metrics-server over a minute. Anticipation explains the ramp (2nd pod Ready 4–9 s after the traffic passes C); fast reaction on the right signal explains the spike.

## 4. Secondary metrics (exploratory, not corrected)

| Load | Metric | Aegis | Default HPA | Tuned HPA |
|---|---|---|---|---|
| Ramp | Seconds degraded | **58** | 123 | 129 |
| Ramp | Pod-minutes (common window) | **15.1** | 18.5 | 15.9 |
| Ramp | 2nd pod requested at (s) | **77** | 148 | 138 |
| Spike | Seconds degraded | **46** | 123 | 113 |
| Spike | Pod-minutes | 13.9 | 15.6 | **12.3** |
| Spike | 2nd pod requested at (s) | **45** | 127 | 103 |
| Waves | Seconds degraded | 66 | **60** | 113 |
| Waves | Pod-minutes | **21.5** | 29.4 | 22.7 |
| Waves | 2nd pod requested at (s) | **75** | 196 | 126 |
| Waves | Re-asks (total in 6 runs) | 1 | 0 | 5 |

- **Degradation:** Aegis is degraded less than half as long as either HPA on the ramp and the spike (p < 0.0001). On the waves it matches the default HPA.
- **Cost (H3):** Aegis uses fewer pod-minutes than the default HPA on all three loads (−8 on the waves). Against the tuned HPA: no difference on the ramp and the waves; **on the spike the tuned HPA uses fewer** (12.3 vs 13.9) while failing 4.4 times more. Aegis is also the most predictable on cost (standard deviation 0.2 pod-minutes against 0.5–4.3).
- **Flapping:** the tuned HPA re-asked 5 times, across its 6 wave runs, for a pod it had given back less than 120 s before; Aegis once.

## 5. Compared with the October campaign

The default HPA failed **16.9%** on the ramp in this campaign, against **37%** in October. The comparison is not like for like, and the October number should no longer be quoted as the HPA's failure rate:

1. **The readiness probe** now runs outside the request queue (`services/catalog-service/src/health.js`) for every autoscaler. A saturated pod no longer drops out of Ready, which also helps the HPA.
2. **The host ran in Performance mode** and its capacity drifted upward during the campaign (C measured 22 → 30 → 24 req/s, [deviation log](design.md#deviation-log)). With the calibration fixed at 22, the pods had more real headroom than Aegis assumed.

What holds across both campaigns is the ranking and the size of the gap: in October Aegis cut the ramp failures from 37% to 2.5%; here from 16.9% to 1.9%.

## 6. Threats to validity

Those of [design.md, section 8](design.md#8-threats-to-validity), plus these, identified after the plan was registered:

| Threat | Effect | Status |
|---|---|---|
| **C drifted up to +36%** within a session | Aegis decided with C = 22 while real capacity was higher: it asked for pods earlier than needed. Works against Aegis on cost, not for it. The block term absorbs the between-session part | Logged; C kept fixed as registered |
| **Unequal variances** | ANOVA p-values are approximate | Post hoc sensitivity (section 2): same direction, 2–5 contrasts significant depending on the analysis |
| **Interim looks** at 2, 3, 4 and 5 blocks | Could tempt an early stop | Nothing was changed and the campaign ran its 6 registered blocks |
| **Load generator on the same node** as the service | k6, Traefik and Prometheus compete for the node with the pods | Same for every autoscaler; not measured |
| **Scale-down rule chosen on October traces of the same loads** | Its cost advantage may be optimistic on unseen traffic | Affects pod-minutes (secondary), not failures |
| **Pod-minutes are only money with per-pod billing** (Fargate, GKE Autopilot) | On fixed nodes, fewer pods save nothing unless the node goes | Declared for the business case |
| **One node, 60m pods, 3 replicas, synthetic load, one tuned HPA** | External validity | Results hold for this lab; production needs its own evaluation |

## 7. What can and cannot be claimed

**Can be claimed** (this lab, these loads): Aegis reduces failed requests against the default HPA on ramps and spikes, and against an HPA tuned in advance on ramps, spikes and waves, with half or less of the time degraded and without using more pods, except on spikes against the tuned HPA.

**Cannot be claimed:** that the benefit comes only from anticipation (H2 refuted); that it holds in production or with tens of replicas; that the October 37% is the HPA's failure rate today.
