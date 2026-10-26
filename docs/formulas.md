# The formulas of Aegis: where they come from and why they fit

Every 5 seconds Aegis answers one question:

> If I do nothing, will the traffic **T seconds from now** be more than the pods I have can serve?

T is the time a new pod needs to be Ready. Asking about "now" is too late: a pod requested now only helps T seconds later. The answer comes from four formulas, each one taken from a well-known field:

| # | Formula | Comes from | What it gives Aegis |
|---|---|---|---|
| 1 | capacity = C · N | Queueing theory | Where the service breaks |
| 2 | r = completed + d(waiting)/dt | Conservation of flow (Little's law) | The traffic that **arrives**, not only the one served |
| 3 | p = r + m · (T + lag) | Linear trend forecasting (least squares) | The traffic T seconds ahead |
| 4 | risk = Φ((p − C·N) / σ) | Normal distribution of forecast errors | How likely it is to go over capacity |
| 5 | σ = √(2 · mean(max(0, e)²)) | Forecast errors, upper semi-deviation | How much to trust the projection |

The decision rule on top of them (70% up, 30% for 60 s down) is hysteresis, the same idea the HPA uses.

## 1. Capacity: C · N

**Where it comes from.** Queueing theory [13][14]. A server that can finish μ requests per second, receiving λ requests per second, is busy a fraction ρ = λ/μ of the time. In the basic model (M/M/1) the mean response time is

$$W = \frac{1}{\mu - \lambda} = \frac{1/\mu}{1 - \rho}$$

While ρ is small, W barely moves. When λ gets close to μ, the denominator goes to 0 and W explodes. Latency is not a slope, it is a **cliff**.

**Why it is useful here.** That is exactly what the service does: P95 of ~0.1–0.3 s until a certain load, and seconds right after. So watching latency is watching the cliff edge from too close: when it rises, it is already too late. The useful question is "will λ pass μ?". C is μ for one pod, in requests per second.

- **C is measured, not computed**: μ depends on the CPU limit, the code, the database and the machine. `python3 -m aegis.calibrate` puts one pod under a step load (+2 req/s every 30 s) and C is the last step before the pod degrades (P95 > L, errors, or it stops keeping up). It is the usual "find the knee" load test, done automatically.
- **× N**: Traefik sends each request to the next pod (round robin), so with N pods each one gets λ/N. The pods are equal, so the capacity adds up.

## 2. Demand: what arrives, not what is served

$$r = \text{completed per second} + \frac{d(\text{requests waiting})}{dt}$$

**Where it comes from.** Conservation of flow, the base of Little's law [15]: what comes in either goes out or stays inside. So arrivals = departures + growth of the queue.

**Why it is useful here.** A pod cannot finish more than μ requests per second. If Aegis counted only finished requests, the number would stop near C exactly when the pod is overloaded, and the rule "scale when demand passes C" could never fire. That happened during development: k6 sent 50 req/s and the pod's own counter showed 29.6. Traefik, at the entrance, gives both terms: completed requests per second, and open connections (one per request in flight), whose derivative is the growth of the queue.

## 3. Projection: p = r + m · (T + lag)

**Where it comes from.** Linear trend extrapolation, the simplest forecasting method with a trend [16]. It is the first-order Taylor approximation r(t + h) ≈ r(t) + r′(t) · h. The slope m is estimated with ordinary least squares over the last 30 s (6 samples), the standard way to fit a linear trend and smooth the noise. Holt's linear trend method (level + trend × horizon) is the same idea [16], and predictive autoscalers use this family of models [4][5][17][18].

**Why the horizon is T + lag.**
- **T** is the provisioning delay, measured by the calibration (from asking for pods until they are Ready). Looking less than T ahead is reacting late; looking much more asks for pods too early.
- **lag**: the demand comes from a rate over a 30 s window, which describes the middle of the window plus one scrape. Measured on a real ramp, it was 19 s behind the traffic k6 was sending; Aegis uses 20 s. Without it, the projection would point to "T − 20 seconds from now".

**Why something this simple.** The horizon is short (~40 s), it runs every 5 s, there is no training data, and every decision has to be explainable. At such short horizons a linear trend is a strong baseline. Its known weakness: when a ramp stops, it keeps projecting the climb for a moment and can ask for one pod too many. Aegis removes it later (rule 6), and the tests measure that cost in pod-minutes.

**Checked against other forecasters** ([forecast.md](tests/forecast.md)). Replayed on the 22 Aegis runs, damped Holt [21] has the lowest error 35 s ahead (MAE 7.2 vs 8.1 req/s; naive 10.9) because it overshoots less when a ramp stops. But with the full decision engine, the linear trend leaves the fewest seconds under capacity (21.6 per run vs 22.8 damped Holt, 26.8 damped linear, 106.9 naive) for the same pod-minutes. Overshooting costs a pod for a minute; undershooting costs failed requests. The linear trend was kept; a forecaster for that asymmetric cost is future work.

## 4. Risk: Φ((p − C·N) / σ)

**Where it comes from.** The projection is never exact. Model the future traffic X as a normal variable centred on the projection, with the typical projection error σ as standard deviation: X ~ N(p, σ²). The probability of going over the capacity is

$$P(X > C N) = 1 - \Phi\left(\frac{C N - p}{\sigma}\right) = \Phi\left(\frac{p - C N}{\sigma}\right)$$

using the symmetry of the normal distribution. Φ is its cumulative distribution function (computed as (1 + erf(z/√2))/2 in `risk.py`). This is how forecasting builds prediction intervals, assuming normal forecast errors [16]. Inventory theory uses the same formula for the probability of running out of stock when demand is normal, and sizes the safety stock with it [20]: Aegis keeps a "stock" of capacity.

**Why a probability and not just "p > C·N".**
- It includes **how reliable the projection is right now**: the same p with noisy traffic (large σ) gives more risk than with steady traffic.
- The threshold has a meaning. Risk = 50% means p = C·N exactly. Risk ≥ 70% means p ≥ C·N + 0.52σ: the projection is over capacity with margin.
- The same formula works for any number of pods: the decision engine asks for the risk with the pods already requested (scale up) and with one less (scale down).

Example with C = 24 req/s, 1 pod, σ = 3: a projection of 24 gives 50%; 25.6 gives 70% (Aegis asks for a pod); 18 gives 2%.

## 5. sigma: learned from the projection's own errors

$$\sigma = \sqrt{2 \cdot \text{mean}\left(\max(0, e)^2\right)}, \quad e = \text{real traffic} - \text{projection}$$

**Where it comes from.** Estimating the spread of the forecast from its past errors is how forecasting methods get their uncertainty [16]. Aegis keeps every projection and, when its moment arrives, compares it with the real traffic. The last 5 minutes are used.

**Why only the positive errors.** Only traffic that comes **above** the projection is dangerous. Using the dangerous side only is the semi-variance (downside risk) idea from finance [19]. For symmetric errors, E[max(0, e)²] = σ²/2, so the factor 2 gives back the usual σ. During development, using both sides made σ jump from 1 to 8–9 req/s when traffic stopped suddenly (the projection was far above the real traffic), which would have made Aegis slow for the next 5 minutes.

**Limits.** σ starts at 2 until there are 6 errors, and never goes under 1 req/s, so a very steady traffic does not make Aegis overconfident.

## 6. The decision rule: 70% up, 30% for 60 s down

Two thresholds and a waiting time are **hysteresis**: the system does not switch back and forth around a single value. The HPA does the same with its stabilization windows [1].

- **Up** when the risk with the pods already requested is ≥ 70%. Using the requested pods (not only the Ready ones) avoids asking for more while a pod is still starting.
- **Down** when the risk with **one pod less** stays under 30% for 60 s. Asking "would I be safe with one less?" instead of "is the risk low now?" avoids removing a pod that is the reason the risk is low.

## Assumptions and limits

| Assumption | Why it holds here | Limit |
|---|---|---|
| Latency depends mainly on req/s | Every request to `/api/books` costs the same (a full Scan) | Mixed workloads need a capacity per request type |
| Pods share the load evenly | Traefik balances request by request | Sticky sessions would break C · N |
| One connection per request | The test traffic uses it (`noConnectionReuse`) | With keep-alive, open connections do not count waiting requests |
| Errors roughly normal | 70% threshold and the σ floor give margin | Very heavy tails would need another distribution |
| Traffic with a trend | Ramps and waves | A sudden jump with no trend before it cannot be anticipated; Aegis then reacts within T |

References: see [references.md](references.md).
