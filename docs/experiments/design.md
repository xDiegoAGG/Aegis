# Experiment design

[Español](design.es.md) · Plan registered on 2026-11-04, **before any run**. What this document fixes (factors, metrics, number of runs, order and analysis) is not changed after seeing results. Any change goes to section 10 with its date and reason.

It complements [methodology.md](methodology.md) (questions, hypotheses and project phases). This document answers *how* those hypotheses are tested and *why that is correct*.

---

## 1. Summary

| | |
|---|---|
| **Design** | Randomized complete block design (RCBD) with 3 × 3 factorial treatments |
| **Factor A: autoscaler** | Aegis · default HPA · tuned HPA |
| **Factor B: load** | Ramp (trend) · Spike (no trend) · Waves (up and down twice) |
| **Blocks** | 6. Every block runs the 9 cells once, in a random order |
| **Runs** | 9 × 6 = **54**, about 13 h (134 min per block), split into sessions of whole blocks |
| **Primary metric** | % of requests the client saw fail (k6) |
| **Primary analysis** | Two-way ANOVA (autoscaler + block) per load; 2 contrasts per load; Holm over 6 contrasts; α = 0.05 |
| **Code** | `scripts/experiments/campaign.py` (order and execution), `design_analysis.py` (analysis), `settings.py` (definition) |

---

## 2. Why the October campaign was replaced

The 2026-10-25 campaign (32 runs) gave a clear signal, but its design has flaws that experimental design theory names as threats to validity [1, 2, 9]:

| Flaw | What happened | Why it matters |
|---|---|---|
| **Confounded with time** | Every Aegis run went from 03:24 to 06:14 UTC; every HPA run from 14:40 to 16:00 UTC | The autoscaler is confounded with the time of day. If the laptop was hotter or busier in the afternoon, that adds to the effect of Aegis and the two cannot be separated. Randomization exists to prevent exactly this [1] |
| **One factor at a time** | Each test changed one thing | Interactions cannot be estimated: if the benefit of Aegis depends on the load (H2), the autoscaler × load interaction must be measured in one design [2, 3] |
| **Arms without a control** | Waves (test 2) and fast ramps (6, 7) with Aegis only | Without a control nothing can be attributed to the autoscaler |
| **n = 3 in several tests** | Tests 2, 6, 7 and 8 | With 3 vs 3 the smallest possible exact p is 0.10: these tests cannot be significant by construction |
| **Weak baseline** | Only the default HPA | Comparing against a rival that is easy to improve threatens construct validity [9]. "Better than the HPA" only means "better than the untuned HPA" |
| **Truncated cost** | `pod_minutes` stopped when the load ended, and the recordings stopped with pods still up | The tail, where pods are left over, was left out, and differently for each autoscaler (the HPA waits 300 s to scale down) |

The October data **is kept** (`docs/tests/test1-…` to `test8-…`) as preliminary evidence and is still read by the dashboard and the reports, but formal conclusions come from this design.

---

## 3. Experimental unit, factors and levels

**Experimental unit:** one run. From the reset (1 Ready pod, no traffic, idle CPU, a freshly created HPA) until k6 ends plus a 360 s tail.

### Factor A: autoscaler (3 levels)

| Level | Configuration | Why it is here |
|---|---|---|
| `aegis` | Aegis writes `minReplicas` (`kubernetes/hpa/aegis.yaml`), with the 15–60 s scale-down rule and the readiness probe in a worker thread | The treatment under evaluation |
| `hpa` | Default HPA: CPU 70%, 300 s scale-down window (`baseline.yaml`) | What almost any untuned cluster runs: the practical reference |
| `hpa-tuned` | Tuned HPA: CPU 50%, 60 s scale-down window (`tuned.yaml`) | **Strong control.** Answers "a well-configured HPA does not need Aegis". Fixed *before* the runs and never adjusted, so the design cannot be accused of handicapping it |

All three levels use the same service image, with the new probe, and the same maximum of 3 replicas. The probe is infrastructure, not part of the treatment: applying it to all keeps the comparison fair.

### Factor B: load (3 levels)

| Level | Profile | What it tests |
|---|---|---|
| `ramp` | `linear.yaml`: 5 → 50 req/s in 2 min, 1 min at the top | H1: with a trend Aegis can anticipate |
| `spike` | `spike.yaml`: 5 → 45 req/s in 5 s | **H2, negative control:** with no trend the theory of Aegis predicts little advantage. If Aegis won as much on the spike as on the ramp, the explanation would be something else (for example, simply having more pods) |
| `waves` | `fluctuating.yaml`: two waves with 2 low minutes between them | H3: scale-down, cost and re-asks (a pod given back and asked for again) |

Loads are scaled by C/24 when they run (`load.py`), so they cross one pod's capacity at the same second whatever C is.

### Factors held constant

Pod image and resources (60m CPU), **host power mode set to "Performance"** (see the 2026-11-04 entry of the deviation log), one minikube node, at most 3 replicas, C and T from a single calibration, 10 s k6 timeout and no connection reuse. Holding nuisance factors constant reduces noise without more runs [2].

---

## 4. Fisher's three principles, and how they are met

Modern experimental design rests on three principles [1, 2, 3].

### 4.1 Randomization

**Theory.** If the order of the treatments is drawn at random, any uncontrolled factor (heat, background processes, caches, drift of C) affects all treatments equally *in expectation*. The effect estimates are then unbiased even though those factors are unknown. Randomization is also what justifies the permutation test [1].

**How.** Inside each block the order of the 9 cells is a different random permutation:

```python
random.Random(DESIGN_SEED * 1000 + block).sample(cells, 9)   # DESIGN_SEED = 20261104
```

The seed is fixed in this document and in `settings.py` before the runs, and the full plan is saved to `docs/tests/design-schedule.json`. Anyone can check that the order was not hand-picked (`python3 campaign.py --plan`).

### 4.2 Replication

**Theory.** Without replication the experimental error cannot be estimated, and without it there is no inference. The number of replicates is chosen by power, not by habit [2, 4].

**How.** 6 replicates of every cell, one per block. Section 6 explains why 6.

### 4.3 Blocking (local control)

**Theory.** When there is a known source of variation that is not of interest (here, the session: day, time, laptop state), units are grouped into homogeneous blocks and treatments are compared *within* blocks. Between-block variation leaves the error, and precision rises without more runs [2, 3].

**How.** A block is one complete replicate of the 9 cells, about 134 min in a row under the same conditions. Sessions always run whole blocks (`--blocks 1-2`), so a difference between nights lands in the block term of the model and does not contaminate the autoscaler comparison. The test `test_blocks_absorb_drift` checks that a large shift between blocks does not change the conclusion.

---

## 5. Metrics

All of them are fixed before the runs.

| Metric | Role | Definition | Why |
|---|---|---|---|
| `failed_percent` | **Primary** | Failed or timed-out (> 10 s) requests ÷ all requests, measured by k6 on the client | What users notice and what costs money. It does not depend on how Kubernetes marks pods (the documented Ready artifact), and it is one number per run |
| `degraded_seconds` | Secondary | Seconds with P95 > 1 s or > 1% failed, for at least 15 s in a row | The operational definition of degradation in [methodology.md](methodology.md) (H1) |
| `pod_minutes_window` | Secondary | Requested pods × time, from k6 start to the end of the load + 360 s | Cost (H3). The window is the same for every run and long enough for even the default HPA (300 s) to be back at 1 pod |
| `first_scale_up_s` | Secondary | Seconds from the start of the load to the request for the 2nd pod | The mechanism: if Aegis anticipates, this is lower |
| `reasks` | Secondary | Scale-ups less than 120 s after a scale-down | Flapping (H3) |

**One primary metric.** With several primary metrics, the chance of finding something "significant" by luck grows with every metric added. Fixing one before seeing the data prevents choosing afterwards whichever looks best [6, 8]. Secondary metrics are all reported, uncorrected and labelled exploratory.

---

## 6. Sample size: why 6 blocks

There are **6 primary contrasts** (2 per load: Aegis against each HPA) with Holm at α = 0.05. The first contrast must pass 0.05 / 6 = **0.0083** [5].

**Power, with the variability measured in October** (standard deviation of failed %: ramp 1.5–2.3, spike 1.7–3.7):

| Blocks | Smallest detectable difference on the ramp (80% power) | On the spike |
|---|---|---|
| 5 | 5.3 points | 8.0 points |
| **6** | **4.6 points** | **6.9 points** |
| 8 | 3.8 points | 5.7 points |

Computation: standard error of a contrast = σ·√(2/b), with (3−1)(b−1) error degrees of freedom; detectable difference ≈ (t₁₋α/₂ + t₀.₈)·standard error. In October the difference against the default HPA was 35 points (ramp) and 42 (spike), so 6 blocks are plenty for H1 against the default HPA. **The difference against the tuned HPA is unknown**: 6 blocks detect it if it is 5–7 points or more; if it is smaller, the result is "no difference shown", and that is what gets reported.

**Why not 5:** the margin is narrower and each block costs the same. **Why not 8:** 4.5 more hours of cluster time to gain 1 point of sensitivity. 6 is the reasonable point.

---

## 7. Analysis plan

Implemented in `scripts/experiments/design_analysis.py` and tested on synthetic data with a known answer (`DesignTest` in `test_tooling.py`).

### 7.1 Model

For each load, the standard randomized block model [2]:

$$y_{ij} = \mu + \tau_i + \beta_j + \varepsilon_{ij}, \qquad i \in \{\text{aegis}, \text{hpa}, \text{hpa-tuned}\},\ j = 1..6$$

τ is the autoscaler effect, β the block effect and ε the error. It is fitted with a two-way ANOVA without interaction (with one observation per cell, the block × treatment interaction *is* the error).

### 7.2 Primary contrasts (H1)

Per load, **Aegis − HPA** and **Aegis − tuned HPA**:

$$t = \frac{\bar y_{\text{aegis}} - \bar y_{\text{hpa}}}{\sqrt{2\,\text{MSE}/b}}, \qquad df = (3-1)(b-1) = 10$$

with a 95% confidence interval for the difference. The 6 p-values are corrected with **Holm** [5], which controls the chance of any false positive (FWER) and is uniformly more powerful than Bonferroni.

**Decision rule, fixed in advance.** H1 holds for a load if Aegis − HPA has a Holm p < 0.05, a negative difference, *and* the rank version (7.4) points the same way. The same rule applies, separately, against the tuned HPA.

### 7.3 Interaction (H2)

If the benefit of Aegis needs a trend, its advantage over the HPA must be larger on the ramp than on the spike. Per block:

$$g_j = (y^{\text{ramp}}_{\text{aegis},j} - y^{\text{ramp}}_{\text{hpa},j}) - (y^{\text{spike}}_{\text{aegis},j} - y^{\text{spike}}_{\text{hpa},j})$$

and a one-sample t test on the g_j (df = b − 1). **H2 holds** if the 95% interval of the mean g is below 0. Pairing by block removes session drift from this comparison.

### 7.4 Robustness

Reported next to every contrast. It does not change the decision rule, except for the fallback in 7.5.

| Test | Purpose |
|---|---|
| **ANOVA on ranks** (rank transform, Conover and Iman [7]) | Assumes no normality. Failed % is bounded at 0 and can be skewed |
| **Within-block randomization test** | *The* test the design itself justifies [1]: swap the labels inside each block (2⁶ = 64 arrangements). Its smallest p is 2/64 = 0.031, so it cannot pass Holm; it confirms the direction but is not the primary test |
| **Cliff's delta** [10] | Assumption-free effect size: −1 means every Aegis run failed less than every HPA run |

### 7.5 Diagnostics and fallback

- **Shapiro-Wilk on the residuals.** If p < 0.05 (not normal), the decision in 7.2 is taken on the rank column, also Holm-corrected. This rule is fixed now so the analysis is not chosen after seeing the data.
- **Mean of every block.** A trend in one direction signals drift between sessions; the block term absorbs it, but it is reported.
- **Drift of C.** At the end of every session C is measured again without saving it (`python3 -m aegis.calibrate --check-only --output docs/tests/calibration-check-<date>.json`). If C dropped more than 10% from the campaign calibration, it goes to section 10 and to the threats to validity.

### 7.6 Secondary (exploratory)

The same model and contrasts for `degraded_seconds`, `pod_minutes_window`, `first_scale_up_s` and `reasks`, with 95% intervals and **no** correction: they describe and generate hypotheses, they do not confirm. **H3** (Aegis uses more pods) is answered by the interval of `pod_minutes_window`, reported whatever it shows.

---

## 8. Threats to validity

Classification of Wohlin et al. [9] and Shadish, Cook and Campbell [11].

| Type | Threat | What the design does | What remains |
|---|---|---|---|
| Internal | Confounding with time or session | Randomization within blocks + blocking | — |
| Internal | Carry-over between runs (pods, recommendations kept by the HPA) | `reset()` deletes the HPA, leaves 1 Ready pod, waits for traffic ≈ 0 and CPU < 30% before every run | Node caches; minimized by the random order |
| Internal | Drift of C | One calibration + a check at the end of every session | Reported if above 10% |
| Construct | Weak baseline | Tuned HPA fixed in advance | Other tunings (request metric, KEDA): out of scope, declared |
| Construct | "Ready" does not reflect real capacity | Primary metric on the client (k6), not in Kubernetes | — |
| Conclusion | Many comparisons | One primary metric, Holm, secondary metrics labelled | — |
| Conclusion | ANOVA assumptions | Diagnostics + rank fallback fixed in advance | — |
| Conclusion | Few replicates | Power computed (section 6) | Differences under 5–7 points against the tuned HPA may go undetected |
| External | One node, small pods, synthetic load | Declared; the loads cover trend, no trend and oscillation | Does not generalize as is to production or to tens of replicas |
| External | The designer also evaluates | Plan registered before the runs, fixed seed, automatic analysis | — |

---

## 9. What does not go to the cluster, and why

| Question | Where it is answered | Why there |
|---|---|---|
| Thresholds (70% / 30%), scale-down wait, horizon | Simulator (`scale_down_sim.py`), with a factorial design on recorded and synthetic traces | Exploring parameters in the cluster would take hundreds of runs. Standard practice is to explore cheaply and confirm expensively [3]: only the chosen configuration goes to the cluster |
| Ramp-speed limit (formerly tests 6 and 7) | Simulator + calibration | It was a one-variable sweep with no control and n = 3; the simulator covers many speeds with the same risk model |
| Metric mode (formerly test 8) | Functional test of 1 run (`run.py test8-metric-mode`) | Another way of connecting Aegis to the HPA, not a hypothesis; not part of the comparison |
| Horizon T (H4) | Calibration (`aegis.calibrate`) and `forecast_accuracy.py` | A measurement of the environment, not a treatment effect |

---

## 10. Protocol

0. **Power mode "Performance", laptop plugged in** (`sudo tuned-adm profile throughput-performance`). Preflight checks it and every run records it (`power_profile`).
1. **Prepare:** `scripts/setup.sh --pod-cpu 60m --build` with the image that has the new probe; check that `kubectl get deploy catalog-service -o yaml` shows readiness on `/ready:3004`.
2. **Calibrate once:** `python3 -m aegis.calibrate`. C and T stay fixed for the whole campaign (`run.py` refuses to mix calibrations within a test).
3. **See the plan:** `python3 scripts/experiments/campaign.py --plan`.
4. **Run in sessions of whole blocks:** `python3 scripts/experiments/campaign.py --blocks 1-2`, then `--blocks 3-4` and `--blocks 5-6`. Preflight runs before every session; if anything fails, the same command resumes it.
5. **Drift check at the end of every session:** `python3 -m aegis.calibrate --check-only --output docs/tests/calibration-check-<date>.json`.
6. **Analyse:** `campaign.py` does it when it ends; by hand, `python3 scripts/experiments/design_analysis.py` → `docs/tests/design-results.md`.
7. **Change nothing mid-campaign:** not the image, not `config.yaml`, not the manifests. If unavoidable, log it below and repeat the affected blocks.

### Deviation log

| Date | Deviation | Reason | Blocks affected |
|---|---|---|---|
| 2026-11-04 | Host power mode added to the held-constant factors and to preflight, **before the first run** | The first calibration gave C = 4 req/s (October: 22) with the host in "balanced". A 60m pod runs in short CPU bursts and the processor does not raise its frequency for them: the same fixed computation cost 21 ms of CPU in the pod against 6.5 ms in "Performance". Ruled out: the new image (an A/B with the previous image gave the same), dependencies (same as the lock) and JIT warm-up (same after 600 requests) | None: no run yet |
| 2026-11-05 | Drift check at the end of the session of blocks 1–3: **measured C = 30 req/s** (two runs: 30, 30) against the campaign calibration C = 22 (+36%, above the 10% threshold). T = 11 s (calibrated: 12 s). `docs/tests/calibration-check-2026-11-05.json` | Host performance changed during the session; consistent with block 1 having more failures than blocks 2 and 3 on all three loads. **C = 22 is kept for blocks 4–6**, as the plan fixes (one calibration): recalibrating would change the Aegis treatment between blocks. The block term absorbs the difference between sessions; within a block the three autoscalers share conditions. With a real C above the one used, Aegis was more conservative (more pods), which works against Aegis on cost, not for it. The check is repeated at the end of every session | All; discussed under threats to validity |
| 2026-11-05 | Drift check at the end of the session of blocks 4–6: **measured C = 24 req/s** (24, 24), +9% over C = 22, within the threshold. T = 12 s. `docs/tests/calibration-check-2026-11-05-end.json`. Also, the first launch of blocks 5–6 stopped at preflight on a false positive of "No other Aegis" (it matched the command line of the session script itself); relaunched unchanged, no run lost | C moved 22 → 30 → 24 during the campaign; the block term absorbs it. No run was discarded or repeated | None |

---

## References

[1] R. A. Fisher, *The Design of Experiments*. Oliver and Boyd, 1935.
[2] D. C. Montgomery, *Design and Analysis of Experiments*, 9th ed. Wiley, 2017. (Ch. 4: randomized complete block designs).
[3] G. E. P. Box, J. S. Hunter, and W. G. Hunter, *Statistics for Experimenters*, 2nd ed. Wiley, 2005.
[4] J. Cohen, *Statistical Power Analysis for the Behavioral Sciences*, 2nd ed. Lawrence Erlbaum, 1988.
[5] S. Holm, "A Simple Sequentially Rejective Multiple Test Procedure," *Scandinavian Journal of Statistics*, vol. 6, no. 2, pp. 65–70, 1979.
[6] B. A. Nosek, C. R. Ebersole, A. C. DeHaven, and D. T. Mellor, "The Preregistration Revolution," *PNAS*, vol. 115, no. 11, pp. 2600–2606, 2018.
[7] W. J. Conover and R. L. Iman, "Rank Transformations as a Bridge Between Parametric and Nonparametric Statistics," *The American Statistician*, vol. 35, no. 3, pp. 124–129, 1981.
[8] R. Jain, *The Art of Computer Systems Performance Analysis*. Wiley, 1991. (Part IV: experimental design for systems).
[9] C. Wohlin, P. Runeson, M. Höst, M. C. Ohlsson, B. Regnell, and A. Wesslén, *Experimentation in Software Engineering*. Springer, 2012.
[10] N. Cliff, "Dominance Statistics: Ordinal Analyses to Answer Ordinal Questions," *Psychological Bulletin*, vol. 114, no. 3, pp. 494–509, 1993.
[11] W. R. Shadish, T. D. Cook, and D. T. Campbell, *Experimental and Quasi-Experimental Designs for Generalized Causal Inference*. Houghton Mifflin, 2002.
