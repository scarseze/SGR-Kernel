import contextvars
import uuid
from contextlib import contextmanager

# Global ContextVars for Distributed Tracing
_trace_id_ctx = contextvars.ContextVar("trace_id", default=None)
_span_id_ctx = contextvars.ContextVar("span_id", default=None)

def get_trace_context() -> dict:
    return {
        "trace_id": _trace_id_ctx.get(),
        "span_id": _span_id_ctx.get()
    }

def set_trace_context(trace_id: str, span_id: str):
    _trace_id_ctx.set(trace_id)
    _span_id_ctx.set(span_id)

@contextmanager
def new_span(trace_id: str = None, parent_span_id: str = None):
    """
    Start a new tracing span.
    If trace_id is not provided, generate a new one (Root Span).
    """
    # 1. Resolve Trace ID
    current_trace = _trace_id_ctx.get()
    if not trace_id:
        trace_id = current_trace or str(uuid.uuid4())
    
    # 2. Generate Span ID
    span_id = str(uuid.uuid4())
    
    # 3. Set Context
    t_token = _trace_id_ctx.set(trace_id)
    s_token = _span_id_ctx.set(span_id)
    
    try:
        yield {"trace_id": trace_id, "span_id": span_id, "parent_span_id": parent_span_id}
    finally:
        _trace_id_ctx.reset(t_token)
        _span_id_ctx.reset(s_token)
