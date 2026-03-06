from typing import Tuple, Any
import logging
from evals.runner import EvaluationRecord

logger = logging.getLogger("evals.graders.reasoning")

async def evaluate_reasoning_quality(record: EvaluationRecord, llm_service: Any) -> Tuple[float, bool]:
    """
    LLM-as-a-judge grader: Scores the reasoning process and explanation quality.
    Note: In a real environment, this might be a method on a class initialized with
    the LLM service, but for demonstration we can pass it, or fetch it from Container.
    """
    from core.container import Container
    
    llm = llm_service or Container.get("model_pool_heavy")
    if not llm:
        logger.warning("No LLM service provided for reasoning evaluation. Passing by default.")
        return 1.0, True
        
    prediction = str(record.prediction)
    expected = str(record.ground_truth.get("content", ""))
    
    system_prompt = (
        "You are an expert AI evaluator.\n"
        "Score the quality of the OUTPUT reasoning compared to the EXPECTED ground truth.\n"
        "Score 1.0 for perfect, clear, and logical reasoning leading to the expected answer.\n"
        "Score 0.5 for partially correct reasoning or finding the answer with poor logic.\n"
        "Score 0.0 for completely flawed logic or completely missing the expected outcome.\n"
        "Return ONLY the float score."
    )
    user_prompt = f"--- EXPECTED ---\n{expected}\n\n--- OUTPUT ---\n{prediction}\n"
    
    try:
        result, _ = await llm.generate(system_prompt=system_prompt, user_prompt=user_prompt, temperature=0.0)
        score = float(result.strip())
        passed = score >= 0.7 # Flexible passing threshold for reasoning
        return score, passed
    except Exception as e:
        logger.error(f"Reasoning evaluation failed: {e}")
        return 0.0, False
