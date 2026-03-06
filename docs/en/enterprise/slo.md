# Service Level Objectives (SLO) & Reliability Contract

This document outlines the operational reliability targets (SLOs) and Error Budgets for the SGR Kernel V3 Enterprise Tier. It serves as the baseline contract for assessing system performance and availability.

## 1. Availability

**Objective**: The SGR Kernel API and Swarm Orchestrator will be available to accept and queue requests 99.9% of the time.

- **SLI (Service Level Indicator)**: Percentage of HTTP 200/202 responses for the `/health/swarm_topology` and `/execute` endpoints over a rolling 30-day window.
- **Error Budget**: 0.1% (approx. 43 minutes of allowed downtime per month).
- **Consequence of Budget Depletion**: Feature freezes. If the error budget is exhausted, all new feature merges are halted, and 100% of engineering effort is redirected to reliability and technical debt reduction until the budget recovers.

## 2. Latency

*Note on Origins: The specific latency thresholds below were established during our Phase 6 Locust Load Testing benchmarks against the Swarm Routing layer under high concurrency.*

**Objective 1 (Routing)**: The core system (Routing, Budgeting, Compliance checks) adds minimal overhead.
- **SLO**: p95 Latency < 500ms for Swarm Orchestrator initialization and pre-flight checks.

**Objective 2 (Inference)**: LLM calls are subject to provider queueing, but local fallback models provide guaranteed bounds for critical paths.
- **SLO**: p95 Latency < 2.0s Time-To-First-Token (TTFT) for `secure_local` tier models.

## 3. Correctness & Compliance

**Objective**: Formal invariants and Output Specifications are strictly enforced.
- **SLO**: 100% compliance with defined `OutputSpec` checks. 0 leakage of formally-banned PII tokens.
- **Error Budget**: 0.0%. A single formal invariant violation breaching the boundary is considered an SEV-1 incident requiring immediate Root Cause Analysis (RCA).

## 4. Alerting Rules (Prometheus/Grafana)
Standard templates provided in the `config/prometheus.yml` repository:
- **`Alert: HighLatency`**: Fires if p95 TTFT > 2s for 5 consecutive minutes.
- **`Alert: ModelHandoffFailing`**: Fires if the `ModelRouter` fails to find an `up` route and defaults to `fallback-none` > 5 times in 10 minutes. 
- **`Alert: BudgetGuardBreachAttempt`**: Fires if an agent attempts to bypass the `TokenLedger` lock.
