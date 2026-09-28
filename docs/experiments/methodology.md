# Experimental Methodology

This document defines the experimental protocol for evaluating Aegis against a reactive HPA baseline. It is the reference for Sprint 1, Sprint 2, and Sprint Final experiment runs. For architecture and parameter definitions, see [architecture/overview.md](../architecture/overview.md).

---

## Research Questions

1. Can a preventive risk-based mechanism reduce latency degradation compared to reactive HPA under the same load conditions?
2. Does the benefit depend on the existence of anticipable traffic signals?
3. Does preventive scaling produce unnecessary scale-out events, and what is their resource cost?
4. What prediction horizon Tp is experimentally reasonable for this cluster and workload?

---

## Operational Definition of Degradation

A service is considered degraded when its P95 request latency exceeds threshold L (milliseconds) continuously for a minimum duration Td (seconds), while the service remains available and processing requests.

Both L and Td are determined empirically during Phase 1 (Characterization). They are not assumed in advance.

---

## Hypotheses

| ID | Hypothesis | Baseline | Primary Metric |
|---|---|---|---|
| H1 | A risk-based preventive mechanism can reduce latency degradation compared to reactive HPA. | Reactive HPA | Duration and magnitude of P95 above L |
| H2 | The benefit depends on the existence of anticipable traffic signals. | Reactive HPA | Performance difference between gradual and abrupt traffic profiles |
| H3 | Preventive scaling can produce unnecessary scale-out events. | Reactive HPA | Additional pods, pod-minutes, and false alarm count |
| H4 | The prediction horizon Tp must be consistent with the actual pod provisioning delay. | Reactive HPA | Pod creation to Ready time vs forecast error at different Tp values |

---

## Experiment Scope

**In scope:**
- Preventive risk estimation
- Pod capacity characterization
- Integration with Prometheus and HPA
- Horizontal scaling only
- Scale-in stabilization strategy
- Controlled load experiments

**Out of scope:**
- Vertical scaling
- Hybrid scaling strategies
- General failure detection or recovery
- Complex forecasting models as MVP requirement
- Custom load balancing logic

**Assumptions:**
- A functional Kubernetes cluster is available.
- MyBookstore can generate reproducible load via k6.
- Prometheus can collect the required metrics.
- HPA can consume the Aegis signal through the available metrics interface.

**Constraints:**
- The test environment has limited capacity; results are interpreted within this experimental scenario.
- Synthetic traffic does not represent all production patterns.

---

## Work Phases

<!-- Diagram: Work phases flow (Characterization to Evaluation) -->
<!-- Insert phase diagram here -->

| Phase | Dominant Question | Activities | Evidence |
|---|---|---|---|
| 1. Characterization | When does the service degrade? | Load tests, RPS to P95 relationship, definition of L and Td, capacity measurement | Initial dataset and capacity curve |
| 2. Ready Time | How long does a replica actually take? | Measure creation to Scheduled to Running to Ready to endpoint registration | Pod ready time distribution |
| 3. MVP Model | Can we anticipate the risk? | Short-term projection, forecast error, probabilistic estimation of L crossing | Model and calibration metrics |
| 4. Integration | Can HPA act on our signal? | Publish metric, configure HPA, test scale-up and scale-down | Functional walking skeleton |
| 5. Stabilization | How do we prevent flapping and waste? | Configure scale-down stabilization windows, measure false alarms | Scale-in policy and overprovisioning metrics |
| 6. Evaluation | Does it outperform reactive HPA? | Gradual and abrupt scenarios, repeated runs, comparison | Quantitative results and threats to validity |

---

## Risks and Mitigations

| Risk | Early Indicator | Mitigation | Contingency |
|---|---|---|---|
| False positives | Many scale-outs without subsequent degradation | Calibrate uncertainty and measure false alarm rate | Adjust threshold, horizon, or fall back to reactive HPA |
| False negatives | Service crosses L before signal exceeds threshold | Test gradual and abrupt scenarios; declare limits | Maintain reactive HPA as safety net |
| Unstable capacity | Same RPS produces very different P95 across runs | Fix resource limits and control experimental conditions | Recalibrate or restrict scenario scope |
| Flapping | Frequent scale-up and scale-down oscillations | Hysteresis and HPA stabilization windows | Increase window or disable scale-in during tests |
| Excessive permissions | Aegis requires broad RBAC access | Apply principle of least privilege | Revoke and revert to standard HPA |
| Schedule slippage | Dependency between infrastructure, data, and model | Build local simulation and initial dataset in parallel | Reduce model scope without abandoning comparison |
