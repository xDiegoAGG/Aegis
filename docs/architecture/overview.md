# Architecture Overview

Aegis is a preventive horizontal scaling mechanism for Kubernetes services. It estimates the probability of latency degradation within a short prediction horizon and publishes that risk as a signal for the HorizontalPodAutoscaler (HPA). Aegis does not replace Kubernetes scheduling or load balancing; it adds a risk-aware input to the standard autoscaling pipeline.

---

## System Component Diagram

<!-- Diagram: System component diagram -->
<!-- Insert architecture diagram here -->

---

## Responsibility Boundaries

Each component owns a strictly defined responsibility. Aegis does not cross these boundaries.

| Component | Responsibility |
|---|---|
| Prometheus | Collect and store time series metrics from the workload. |
| Aegis Core | Query metrics, estimate risk of latency degradation, publish risk metric. |
| Custom Metrics Adapter | Expose the Aegis risk metric through the Kubernetes Metrics API. |
| HPA | Read the custom metric and adjust the desired replica count on the Deployment. |
| Deployment / ReplicaSet | Create and maintain pod replicas according to the desired count. |
| Scheduler | Place new pods onto cluster nodes. |
| Readiness probe | Determine when a pod is ready to receive traffic. |
| Service | Route traffic to all Ready pods registered as endpoints. |

Aegis interacts with Prometheus (reads) and the Custom Metrics Adapter (writes). It does not call the Kubernetes API to create pods, modify deployments, or redirect traffic directly.

---

## Aegis Internal Pipeline

The pipeline runs on a configurable polling interval. Each cycle executes the following stages in order.

<!-- Diagram: Aegis internal pipeline (9 stages) -->
<!-- Insert pipeline flowchart here -->

---

## Preventive vs Reactive Scaling: Conceptual Sequence

The central argument of the project is temporal. A reactive controller detects degradation after it has started. A preventive controller acts before it starts, assuming the provisioning delay is known.

<!-- Diagram: Preventive vs reactive sequence (Aegis vs standard HPA) -->
<!-- Insert sequence diagram here -->

---

## Key Parameters

| Parameter | Definition | How it is determined |
|---|---|---|
| L | P95 latency threshold that defines degradation | Empirical load tests on the reference service (OE1) |
| Td | Minimum continuous duration above L to confirm degradation | Defined after characterization experiments (OE1) |
| Tp | Prediction horizon for risk estimation | Empirical measurement of Pod creation to Ready time (OE2) |
| sigma | Uncertainty of the short-term demand forecast | Computed from residual errors of recent projections (OE3) |
| Risk threshold | Risk score level at which HPA is triggered | Calibrated during MVP integration (OE4) |
