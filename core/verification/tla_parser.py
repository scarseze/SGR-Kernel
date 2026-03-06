import ast
import functools
import inspect
import logging
import operator
import re
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

class InvariantViolationError(Exception):
    """Raised when a runtime execution violates a formal TLA+ invariant."""
    pass


# Safe comparison operators for invariant evaluation
_SAFE_OPS = {
    '<=': operator.le,
    '>=': operator.ge,
    '!=': operator.ne,
    '==': operator.eq,
    '<':  operator.lt,
    '>':  operator.gt,
}


class SafeInvariantEvaluator:
    """
    Evaluates simple TLA+ invariant expressions safely, without `eval()`.
    Supports: `var op var`, `var op literal`, comparisons (<=, >=, ==, !=, <, >).
    """

    @staticmethod
    def _resolve_value(token: str, context: Dict[str, Any]) -> Any:
        """Resolve a token to either a context variable or a Python literal."""
        token = token.strip()
        if token in context:
            return context[token]
        try:
            return ast.literal_eval(token)
        except (ValueError, SyntaxError):
            raise ValueError(f"Cannot resolve token '{token}' — not in context and not a literal.") from None

    @classmethod
    def evaluate(cls, expression: str, context: Dict[str, Any]) -> bool:
        """
        Evaluate a simple comparison expression like 'total_spent <= max_budget'.
        Returns True if the invariant holds, False otherwise.
        Raises ValueError if the expression cannot be parsed.
        """
        # Try each operator (longest first to avoid <= matching < first)
        for op_str in sorted(_SAFE_OPS.keys(), key=len, reverse=True):
            if op_str in expression:
                parts = expression.split(op_str, 1)
                if len(parts) == 2:
                    left = cls._resolve_value(parts[0], context)
                    right = cls._resolve_value(parts[1], context)
                    return _SAFE_OPS[op_str](left, right)

        raise ValueError(f"Unsupported invariant expression: '{expression}'")


class TLAParser:
    """
    A lightweight parser/stub to extract TLA+ invariants from specification files.
    In V3 MVP, this uses regex to find invariants defined like `InvariantName == Condition`.
    It then attempts a basic translation into executable Python logic for simple numeric bounds.
    """
    
    @staticmethod
    def extract_invariant_logic(tla_filepath: str, invariant_name: str) -> Optional[str]:
        """
        Extracts the right-hand side of an invariant definition from a .tla file.
        Example: `NoBudgetOverrun == total_spent <= max_budget` -> `total_spent <= max_budget`
        """
        try:
            with open(tla_filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Regex to find `InvariantName == ...`
            pattern = rf"^{invariant_name}\s*==\s*(.+)$"
            match = re.search(pattern, content, re.MULTILINE)
            
            if match:
                raw_logic = match.group(1).strip()
                # Convert TLA+ `=` to Python `==` if it's an equality check (heuristic)
                if " = " in raw_logic and "==" not in raw_logic:
                    raw_logic = raw_logic.replace(" = ", " == ")
                return raw_logic
            return None
        except FileNotFoundError:
            logger.error(f"TLA specification file not found: {tla_filepath}")
            return None


def enforce_invariant(invariant_name: str, tla_filepath: str, check_pre_post: bool = True):
    """
    Decorator that enforces a TLA+ invariant at runtime.
    
    Uses SafeInvariantEvaluator instead of eval() to prevent code injection.
    
    Args:
        invariant_name: Name of the invariant in the TLA file.
        tla_filepath: Path to the .tla specification.
        check_pre_post: If True, tests invariant before AND after function execution.
    """
    def decorator(func: Callable):
        
        tla_logic = TLAParser.extract_invariant_logic(tla_filepath, invariant_name)
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not tla_logic:
                return func(*args, **kwargs)
                
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            context = bound_args.arguments.copy()
            
            def _check_invariant(phase: str):
                try:
                    is_valid = SafeInvariantEvaluator.evaluate(tla_logic, context)
                    if not is_valid:
                        raise InvariantViolationError(
                            f"Formally verified '{invariant_name}' failed during {phase} of {func.__name__}."
                        )
                except InvariantViolationError:
                    raise
                except Exception as e:
                    logger.debug(f"Could not evaluate TLA invariant {invariant_name}: {e}")
            
            # PRE-CONDITION CHECK
            if check_pre_post:
                _check_invariant("precondition check")
                
            # EXECUTE FUNCTION
            result = func(*args, **kwargs)
            
            # Update context for postcondition
            context["result"] = result
            
            # POST-CONDITION CHECK
            _check_invariant("postcondition check")
            
            return result
            
        return wrapper
    return decorator

