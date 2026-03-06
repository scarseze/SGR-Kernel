import logging
from abc import ABC, abstractmethod
from typing import Any, Tuple

logger = logging.getLogger("core.metrics")


class EvaluationMetric(ABC):
    def __init__(self, name: str, threshold: float = 1.0) -> None:
        self.name = name
        self.threshold = threshold

    @abstractmethod
    async def measure(self, **kwargs: Any) -> float:
        """Returns a score between 0.0 and 1.0."""
        pass

    async def passes(self, **kwargs: Any) -> Tuple[bool, str, float]:
        """Returns (passed, reason, score)"""
        try:
            score = await self.measure(**kwargs)
            passed = score >= self.threshold
            reason = f"[{self.name}] Score {score:.2f} (Threshold: {self.threshold})"
            return passed, reason, score
        except Exception as e:
            logger.error(f"Metric {self.name} evaluation failed: {e}")
            return False, f"[{self.name}] Error during evaluation: {e}", 0.0


class CostLimitMetric(EvaluationMetric):
    def __init__(self, max_cost_usd: float) -> None:
        super().__init__("CostLimit", threshold=1.0)
        self.max_cost_usd = max_cost_usd

    async def measure(self, current_cost_usd: float = 0.0, **kwargs: Any) -> float:
        if current_cost_usd <= self.max_cost_usd:
            return 1.0
        return 0.0


class FaithfulnessMetric(EvaluationMetric):
    def __init__(self, llm_service: Any, threshold: float = 0.7) -> None:
        super().__init__("Faithfulness", threshold=threshold)
        self.llm = llm_service

    async def measure(self, output: str = "", context: str = "", **kwargs: Any) -> float:
        if not context:
            return 1.0  # If no context, cannot be unfaithful to it

        system_prompt = (
            "You are an objective evaluator scoring Faithfulness.\n"
            "Compare the OUTPUT to the provided CONTEXT.\n"
            "Score 1.0 if the OUTPUT derives its claims entirely from the CONTEXT without contradicting it.\n"
            "Score 0.0 if the OUTPUT contains claims completely unsupported by or contradicting the CONTEXT (hallucinations).\n"
            "Return ONLY a float number, no other text."
        )
        user_prompt = f"--- CONTEXT ---\n{context}\n\n--- OUTPUT ---\n{output}\n"

        try:
            result, _ = await self.llm.generate(system_prompt=system_prompt, user_prompt=user_prompt, temperature=0.0)
            return float(result.strip())
        except ValueError:
            logger.warning(f"FaithfulnessMetric parsed non-float: {result}")
            return 0.0
        except Exception as e:
            logger.error(f"FaithfulnessMetric error: {e}")
            return 0.0


class AnswerRelevancyMetric(EvaluationMetric):
    def __init__(self, llm_service: Any, threshold: float = 0.7) -> None:
        super().__init__("AnswerRelevancy", threshold=threshold)
        self.llm = llm_service

    async def measure(self, output: str = "", query: str = "", **kwargs: Any) -> float:
        if not query:
            return 1.0

        system_prompt = (
            "You are an objective metric scoring Answer Relevancy.\n"
            "Score how relevant the OUTPUT is to the original QUERY on a scale from 0.0 to 1.0.\n"
            "1.0 means perfectly directly answers the query without getting off-topic. 0.0 means completely irrelevant.\n"
            "Return ONLY a float number, no other text."
        )
        user_prompt = f"--- QUERY ---\n{query}\n\n--- OUTPUT ---\n{output}\n"

        try:
            result, _ = await self.llm.generate(system_prompt=system_prompt, user_prompt=user_prompt, temperature=0.0)
            return float(result.strip())
        except ValueError:
            logger.warning(f"AnswerRelevancyMetric parsed non-float: {result}")
            return 0.0
        except Exception as e:
            logger.error(f"AnswerRelevancyMetric error: {e}")
            return 0.0


class RequirementsMetric(EvaluationMetric):
    """Fallback metric to represent the old string-based requirements evaluation"""
    def __init__(self, llm_service: Any, requirements: str) -> None:
        super().__init__("RequirementsMatch", threshold=1.0)
        self.llm = llm_service
        self.requirements = requirements

    async def measure(self, output: str = "", **kwargs: Any) -> float:
        if not self.requirements:
            return 1.0

        system_prompt = (
            "You are a strict, objective Evaluator.\n"
            "Score whether the OUTPUT meets the REQUIREMENTS.\n"
            "Score 1.0 if it fully satisfies them. Score 0.0 if it fails.\n"
            "Return ONLY a float number."
        )
        user_prompt = f"--- REQUIREMENTS ---\n{self.requirements}\n\n--- OUTPUT ---\n{output}\n"

        try:
            result, _ = await self.llm.generate(system_prompt=system_prompt, user_prompt=user_prompt, temperature=0.0)
            return float(result.strip())
        except Exception:
            # Fallback to keyword matching if LLM fails
            output_str = str(output).lower()
            requirement_keywords = [w.strip().lower() for w in self.requirements.split(",") if w.strip()]
            matched = [kw for kw in requirement_keywords if kw in output_str]
            match_ratio = len(matched) / len(requirement_keywords) if requirement_keywords else 1.0
            return 1.0 if match_ratio >= 0.5 else 0.0
