from typing import Any, Dict

from jinja2 import BaseLoader
from jinja2.nativetypes import NativeEnvironment


def resolve_inputs(template: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively resolves string values in the template dict using Jinja2 syntax
    against the provided context.
    """
    env = NativeEnvironment(loader=BaseLoader())
    
    def _resolve(obj):
        if isinstance(obj, dict):
            return {k: _resolve(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [_resolve(item) for item in obj]
        elif isinstance(obj, str):
            if "{{" in obj and "}}" in obj:
                try:
                    # Convention: {{ step_id.path }} or {{ step_id.output.path }}
                    # We wrap context to support both
                    wrapped_context = {}
                    for k, v in context.items():
                        if isinstance(v, dict):
                            wrapped_context[k] = {**v, "output": v}
                        else:
                            wrapped_context[k] = {"output": v}
                    
                    return env.from_string(obj).render(**wrapped_context)
                except Exception:
                    return obj # Fallback
            return obj
        else:
            return obj

    return _resolve(template)
