from typing import Tuple

from evals.runner import EvaluationRecord


async def evaluate_exact_match(record: EvaluationRecord) -> Tuple[float, bool]:
    """
    Deterministic grader: strictly checks if the prediction matches ground truth exactly.
    """
    prediction = str(record.prediction).strip().lower()
    expected = str(record.ground_truth.get("content", "")).strip().lower()

    if prediction == expected:
        return 1.0, True

    # If the exact match fails, maybe it's contained within the prediction
    if expected in prediction:
        return 0.5, False  # Partial score, but didn't pass strict exact match

    return 0.0, False
