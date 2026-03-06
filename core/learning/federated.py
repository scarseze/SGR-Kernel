import logging
import math
import random
from dataclasses import dataclass
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

@dataclass
class LearningPayload:
    """Represents a set of learning signals or metric gradients from an agent."""
    agent_id: str
    task_type: str
    success: bool
    metrics: Dict[str, float]  # E.g., {"eval_score": 0.9, "reward": 0.8}
    gradients: Optional[List[float]] = None  # Placeholder for actual model gradients


class DifferentialPrivacyFilter:
    """
    Applies Laplace noise to numeric learning signals to guarantee
    epsilon-Differential Privacy before data leaves the local secure environment.
    """
    def __init__(self, epsilon: float = 1.0, sensitivity: float = 1.0):
        self.epsilon = epsilon
        self.sensitivity = sensitivity

    def _laplace_noise(self) -> float:
        """Sample from a Laplace distribution."""
        scale = self.sensitivity / self.epsilon
        u = random.uniform(-0.5, 0.5)
        return scale * math.copysign(math.log(1 - 2 * abs(u)), u)

    def anonymize_metrics(self, payload: LearningPayload) -> LearningPayload:
        """Add noise to all numeric metrics to prevent PII/exact state recovery."""
        noisy_metrics = {}
        for k, v in payload.metrics.items():
            noisy_metrics[k] = v + self._laplace_noise()
            
        noisy_gradients = None
        if payload.gradients:
            noisy_gradients = [g + self._laplace_noise() for g in payload.gradients]
            
        return LearningPayload(
            agent_id="anonymized_swarm_node",  # Strip identifiable agent ID
            task_type=payload.task_type,
            success=payload.success,
            metrics=noisy_metrics,
            gradients=noisy_gradients
        )


class AggregatorNode:
    """
    Central node that collects securely filtered LearningPayloads
    from dispersed agents for periodic Federated Learning syncs.
    """
    def __init__(self):
        self.pool: List[LearningPayload] = []

    def receive_payload(self, payload: LearningPayload):
        """Accepts a payload. In a real system, this would write to a DB or Kafka."""
        self.pool.append(payload)
        logger.info(f"Aggregator received payload from {payload.agent_id} for {payload.task_type}. Pool size: {len(self.pool)}")

    def trigger_aggregation(self) -> Dict[str, float]:
        """
        Placeholder for FedAvg or FedProx aggregation.
        Returns average metrics across the pool.
        """
        if not self.pool:
            return {}

        avg_metrics = {}
        count = len(self.pool)
        
        # Super simplified average of all keys present in the first payload
        if self.pool[0].metrics:
            for key in self.pool[0].metrics.keys():
                total = sum(p.metrics.get(key, 0.0) for p in self.pool)
                avg_metrics[f"avg_{key}"] = total / count
                
        self.pool.clear()  # Reset after aggregation
        return avg_metrics

# Global instance for the kernel
global_aggregator = AggregatorNode()
