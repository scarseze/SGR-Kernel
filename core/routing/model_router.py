import logging
from typing import Dict

logger = logging.getLogger(__name__)

class ModelRoute:
    def __init__(self, name: str, cost_multiplier: float, max_context: int, is_local: bool = False):
        self.name = name
        self.cost_multiplier = cost_multiplier
        self.max_context = max_context
        self.is_local = is_local
        self.status = "up"  # "up", "down", "degraded"

class ModelRouter:
    """
    Handles Zero-Downtime Model Swapping (Blue-Green AI).
    Routes prompts to the best available model based on health and rules.
    """
    def __init__(self):
        # Default tier structure
        self.registry: Dict[str, ModelRoute] = {
            "primary": ModelRoute("gpt-4-turbo", 1.0, 128000),
            "fallback": ModelRoute("gpt-3.5-turbo", 0.1, 16000),
            "secure_local": ModelRoute("ollama/qwen2.5", 0.0, 8000, is_local=True)
        }
        self.current_route = "primary"

    def register_route(self, route_id: str, model_name: str, cost: float, context: int, local: bool = False):
        self.registry[route_id] = ModelRoute(model_name, cost, context, local)

    def mark_down(self, route_id: str):
        if route_id in self.registry:
            self.registry[route_id].status = "down"
            logger.warning(f"Router: Model route '{route_id}' marked DOWN.")

    def mark_up(self, route_id: str):
        if route_id in self.registry:
            self.registry[route_id].status = "up"
            logger.info(f"Router: Model route '{route_id}' marked UP.")

    def get_best_route(self, requires_local: bool = False, max_cost: float = float('inf')) -> ModelRoute:
        """Find the next best available model route based on constraints."""
        candidates = []
        for _route_id, route in self.registry.items():
            if route.status != "up":
                continue
            if requires_local and not route.is_local:
                continue
            if route.cost_multiplier > max_cost:
                continue
            candidates.append(route)
        
        if not candidates:
            # Absolute last resort fallback
            logger.error("Router: No optimal routes available. Defaulting to fallback-none.")
            return ModelRoute("fallback-none", 0.0, 4000)
            
        # Sort by capability (max context) then cost, depending on heuristic
        # For our basic heuristic, we just want the most capable one that fits constraints
        best_route = sorted(candidates, key=lambda x: x.max_context, reverse=True)[0]
        return best_route
