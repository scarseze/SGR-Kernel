"""
Critic Engine for SGR Kernel.
Evaluates step outputs against requirements using LLM-based analysis.
"""

from typing import Any, Dict, Tuple


class CriticEngine:
    def __init__(self, llm_service: Any):
        self.llm = llm_service

    async def evaluate(
        self, step_id: str, skill_name: str, inputs: Dict[str, Any], output: Any, requirements: str = ""
    ) -> Tuple[bool, str]:  # (Passed, Reason)
        """
        Run a Critic pass on the output.
        If no requirements are provided, automatically passes.
        Otherwise, checks output against the requirements using keyword matching.
        """
        if not requirements:
            return True, "No specific requirements."

        output_str = str(output).lower()
        requirement_keywords = [w.strip().lower() for w in requirements.split(",") if w.strip()]

        if not requirement_keywords:
            return True, "No parsable requirements."

        matched = [kw for kw in requirement_keywords if kw in output_str]
        match_ratio = len(matched) / len(requirement_keywords)

        if match_ratio >= 0.5:
            return True, f"Critic passed: {len(matched)}/{len(requirement_keywords)} requirement keywords found in output."
        else:
            return False, f"Critic failed: only {len(matched)}/{len(requirement_keywords)} requirement keywords matched."
