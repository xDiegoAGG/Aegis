# Aegis

Preventive horizontal scaling mechanism for Kubernetes services.

Aegis estimates the probability of latency degradation within a short prediction horizon ($T_p$) and publishes that risk as a signal for the standard Kubernetes Horizontal Pod Autoscaler (HPA). By scaling capacity ahead of demand spikes, Aegis closes the 1.5 to 3-minute reactivity lag inherent in traditional autoscalers without requiring expensive 24/7 overprovisioning.

---

## Documentation

* **Business Case & ROI:** [docs/business_case.md](docs/business_case.md)
  Executive pitch, FinOps analysis, ROI formulas, and industry evidence on the cost of latency.
* **Architecture Overview:** [docs/architecture/overview.md](docs/architecture/overview.md)
  System design, responsibility boundaries, Aegis internal pipeline, and key parameters ($L$, $T_d$, $T_p$, $\sigma$).
* **Experimental Methodology:** [docs/experiments/methodology.md](docs/experiments/methodology.md)
  Validation protocol, hypotheses (H1 to H4), evaluation phases, and test workloads (MyBookstore).
* **Project Bibliography:** [docs/references.md](docs/references.md)
  Foundational academic literature and Kubernetes documentation.
