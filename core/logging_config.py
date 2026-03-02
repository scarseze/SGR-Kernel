
import logging
import os
import sys

from fluent import handler


def setup_logging(service_name: str, host: str = "localhost", port: int = 24224):
    """
    Configures the root logger to send logs to Fluent Bit.
    falls back to stdout if connection fails (managed by fluent-logger).
    """
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # 1. Console Handler (for docker logs)
    console_handler = logging.StreamHandler(sys.stdout)
    console_formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # 2. Fluent Handler (for ELK)
    # Get host from env or default
    fluent_host = os.getenv("FLUENT_BIT_HOST", host)
    fluent_port = int(os.getenv("FLUENT_BIT_PORT", port))

    try:
        from core.tracing import get_trace_context

        # custom_format is a dict that will be merged with log record
        h = handler.FluentHandler(
            f"sgr.{service_name}",
            host=fluent_host,
            port=fluent_port
        )
        
        # Let's use a formatter that creates a JSON-like structure key
        class FluentFormatter(handler.FluentRecordFormatter):
            def format(self, record):
                data = super().format(record)
                # Add extra fields
                data['service'] = service_name
                
                # Distributed Tracing Context
                ctx = get_trace_context()
                if ctx.get("trace_id"):
                    data['trace_id'] = ctx['trace_id']
                if ctx.get("span_id"):
                    data['span_id'] = ctx['span_id']
                
                return data

        formatter = FluentFormatter({
            'level': '%(levelname)s',
            'hostname': '%(hostname)s',
            'where': '%(module)s.%(funcName)s',
            'message': '%(message)s',
        })
        
        h.setFormatter(formatter)
        logger.addHandler(h)
        logging.info(f"✅ Fluent logging enabled: {fluent_host}:{fluent_port}")

    except Exception as e:
        logging.warning(f"❌ Failed to setup Fluent logging: {e}")

    return logger
