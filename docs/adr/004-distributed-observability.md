# 4. Distributed Observability

Date: 2026-03-06

## Status

Accepted

## Context

The SGR Kernel operates as a distributed system, encompassing the Core API, disparate Worker nodes, a Telegram Bot proxy, and specialized databases. Diagnosing issues, measuring end-to-end latency, and understanding the causal relationship between asynchronous events (e.g., step scheduled -> step executed -> critic evaluation) is highly complex without centralized tracing.

## Decision

We adopted OpenTelemetry (OTel) as the standard for distributed tracing and Prometheus for metric aggregation.
1. `TelemetryManager` was introduced to bootstrap OTLP Exporters.
2. Traces are exported to a central Jaeger instance via the `OTEL_EXPORTER_OTLP_ENDPOINT` environment variable.
3. Every request is assigned a `trace_id` (usually mapping to `request_id`) which propagates across the Execution Graph and worker boundaries.
4. Metrics (e.g., `sgr_active_jobs_total`, `sgr_memory_vector_searches_total`) are exposed via Prometheus servers running on dedicated ports.

## Consequences

- **Pros**: Complete visibility into the execution DAG. Ability to visualize bottlenecks (e.g., slow LLM inference vs. slow database queries).
- **Cons**: Adds overhead to performance. Requires maintaining observability infrastructure (Jaeger, Prometheus, Grafana) in the deployment footprint.
