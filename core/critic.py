"""
Critic Engine for SGR Kernel.
Evaluates step outputs against requirements using LLM-based analysis.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

logger = logging.getLogger("core.critic")

class CriticResponse(BaseModel):
    passed: bool = Field(..., description="True if output satisfies the requirements, False otherwise.")
    reason: str = Field(..., description="Brief explanation of why it passed or failed.")

class CriticEngine:
    def __init__(self, llm_service: Any):
        # llm_service is expected to be an LLMService instance (e.g., model_pool.heavy)
        self.llm = llm_service

    async def evaluate(
        self, step_id: str, skill_name: str, inputs: Dict[str, Any], output: Any, requirements: str = "", metrics: Optional[List[Any]] = None
    ) -> Tuple[bool, str]:  # (Passed, Reason)
        """
        Run a Critic pass on the output using EvaluationMetrics.
        Maintains backward compatibility by converting `requirements` into a `RequirementsMetric`.
        """
        from core.metrics import RequirementsMetric
        
        eval_metrics = metrics or []
        if requirements:
            eval_metrics.append(RequirementsMetric(self.llm, requirements))

        if not eval_metrics:
            return True, "No specific requirements or metrics."

        logger.debug(f"Critic evaluating step {step_id} against {len(eval_metrics)} metrics...")
        reasons = []
        
        # Prepare standard kwargs for metrics
        kwargs = {
            "output": str(output),
            "context": str(inputs),
            "query": str(inputs.get("query", "")) or str(inputs),
            "requirements": requirements
        }

        try:
            for metric in eval_metrics:
                passed, reason, score = await metric.passes(**kwargs)
                reasons.append(reason)
                if not passed:
                    return False, f"Failed metric: {reason}"
                    
            return True, "All metrics passed: " + "; ".join(reasons)
        except Exception as e:
            logger.error(f"Critic evaluation failed: {e}. Defaulting to fallback pass.")
            return True, f"Fallback pass (Error during evaluation): {e}"

    async def evaluate_plan(
        self, agent_name: str, tool_calls_data: List[Dict[str, Any]], history: List[Dict[str, Any]], requirements: str = "", metrics: Optional[List[Any]] = None
    ) -> Tuple[bool, str]:  # (Passed, Reason)
        """
        Evaluate an LLM's proposed plan (tool calls) before execution using EvaluationMetrics.
        """
        from core.metrics import RequirementsMetric
        
        eval_metrics = metrics or []
        
        if requirements:
            # Wrap the old Plan Critic system prompt logic into a requirements metric format
            plan_requirements = (
                f"Evaluate whether the proposed action sequence is logical, safe, and satisfies: {requirements}.\n"
                f"Agent Name: {agent_name}"
            )
            eval_metrics.append(RequirementsMetric(self.llm, plan_requirements))

        if not eval_metrics:
            return True, "No specific plan requirements or metrics."

        # Keep history concise for context
        condensed_history = history[-5:] if len(history) > 5 else history
        
        kwargs = {
            "output": str(tool_calls_data),
            "context": str(condensed_history),
            "query": str(condensed_history[-1] if condensed_history else "")
        }

        try:
            logger.debug(f"Plan Critic evaluating proposed tool calls from agent {agent_name}...")
            reasons = []
            for metric in eval_metrics:
                passed, reason, score = await metric.passes(**kwargs)
                reasons.append(reason)
                if not passed:
                    return False, f"Plan failed metric: {reason}"

            return True, "Plan passed all metrics: " + "; ".join(reasons)
        except Exception as e:
            logger.error(f"Plan Critic LLM evaluation failed: {e}. Defaulting to safe (pass).")
            return True, "Fallback pass: Critic LLM unavailable."
