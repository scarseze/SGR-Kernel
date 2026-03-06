import logging
import os
from contextlib import contextmanager
from typing import Any

logger = logging.getLogger("core.telemetry")

# Global Telemetry Instance
_telemetry_instance = None


class TelemetryManager:
    def __init__(self, service_name: str = "sgr-kernel", endpoint: str = "http://jaeger:4317"):
        self.enabled = False
        self.tracer = None
        self.meter = None
        self.prom_enabled = False

        try:
            from opentelemetry import metrics, trace
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased

            # Configure Sampler from Environment
            sample_rate = float(os.getenv("OTEL_TRACE_SAMPLE_RATE", "0.1"))
            sampler = ParentBased(root=TraceIdRatioBased(sample_rate))
            logger.info(f"Otel Sampler: {sampler} (Rate: {sample_rate})")

            # 1. Tracing
            resource = Resource.create({"service.name": service_name})
            trace_provider = TracerProvider(resource=resource, sampler=sampler)
            if endpoint:
                try:
                    otlp_exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
                    span_processor = BatchSpanProcessor(otlp_exporter)
                    trace_provider.add_span_processor(span_processor)
                    logger.info(f"OpenTelemetry Tracing enabled (endpoint: {endpoint})")
                except Exception as e:
                    logger.warning(f"Failed to configure OTLP exporter: {e}")

            # Check if provider already set to avoid error in tests/re-init
            # trace.get_tracer_provider() returns a Proxy or NoOp by default.
            # We just set it. If it fails, we catch it? No, otel warns usually.
            # But let's only set if it's not already ours.
            try:
                trace.set_tracer_provider(trace_provider)
            except Exception:
                # Provider might be already set (e.g. during tests)
                pass

            self.tracer = trace.get_tracer(service_name)

            # 2. Metrics (Placeholder for now, or Prometheus if library allows)
            # For now standard print or no-op
            self.meter = metrics.get_meter(service_name)

            self.enabled = True

        except ImportError:
            logger.warning(
                "OpenTelemetry packages not found. Telemetry disabled. Install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp"
            )
            self.enabled = False
        except Exception as e:
            logger.error(f"Failed to initialize Telemetry: {e}")
            self.enabled = False

        # 3. Prometheus Metrics Initialization
        try:
            from prometheus_client import Counter, Histogram
            
            self.token_counter = Counter(
                "sgr_kernel_llm_tokens_total", 
                "Total number of tokens consumed by the LLM", 
                ["agent", "model"]
            )
            
            self.latency_histogram = Histogram(
                "sgr_kernel_llm_latency_seconds", 
                "Latency of LLM responses in seconds", 
                ["agent", "model"]
            )
            
            self.handoff_counter = Counter(
                "sgr_kernel_agent_handoffs_total", 
                "Total number of handoffs between agents", 
                ["from_agent", "to_agent"]
            )
            
            self.prom_enabled = True
        except ImportError:
            logger.warning("prometheus_client not installed, metrics disabled.")
            self.prom_enabled = False
        except Exception as e:
            logger.error(f"Failed to initialize Prometheus metrics: {e}")
            self.prom_enabled = False

    def start_metrics_server(self, port: int = 8001) -> None:
        if self.prom_enabled:
            try:
                from prometheus_client import start_http_server
                start_http_server(port)
                logger.info(f"Prometheus metrics server started on port {port}")
            except Exception as e:
                logger.error(f"Failed to start Prometheus metrics server: {e}")

    def record_llm_call(self, agent: str, model: str, tokens: int, latency_ms: float) -> None:
        if self.prom_enabled:
            self.token_counter.labels(agent=agent, model=model).inc(tokens)
            self.latency_histogram.labels(agent=agent, model=model).observe(latency_ms / 1000.0)

    def record_handoff(self, from_agent: str, to_agent: str) -> None:
        if self.prom_enabled:
            self.handoff_counter.labels(from_agent=from_agent, to_agent=to_agent).inc()

    @contextmanager
    def span(self, name: str, attributes: dict[str, Any] | None = None) -> Any:
        """Context manager for creating a span. 
        Note: Error-based sampling requires Tail-Based Sampling at the OTel Collector level.
        The current Head-Based Sampler (TraceIdRatioBasedSampler) decides sampling at span start.
        """
        if not self.enabled or not self.tracer:
            yield None
            return

        from opentelemetry.trace.status import Status, StatusCode
        with self.tracer.start_as_current_span(name, attributes=attributes or {}) as span:
            try:
                yield span
            except Exception as e:
                # OTel Python Head-based sampling might drop this. 
                # Strict error sampling MUST be configured at the OTel Collector (Tail-Based).
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise

    def log_metric(self, name: str, value: float, attributes: dict[str, Any] | None = None) -> None:
        """Log a metric (Counter/Gauge placeholder)."""
        if not self.enabled:
            return
        logger.info(f"[METRIC] {name}={value} {attributes or {}}")

    def record_metric(self, name: str, value: float, attributes: dict[str, Any] | None = None) -> None:
        """Alias for log_metric — used by SwarmEngine for subswarm_depth tracking."""
        self.log_metric(name, value, attributes)


def init_telemetry(service_name: str = "sgr-kernel") -> TelemetryManager:
    global _telemetry_instance
    if _telemetry_instance:
        return _telemetry_instance

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://jaeger:4317")
    _telemetry_instance = TelemetryManager(service_name, endpoint)
    return _telemetry_instance


def get_telemetry() -> TelemetryManager:
    global _telemetry_instance
    if not _telemetry_instance:
        return init_telemetry()
    return _telemetry_instance
