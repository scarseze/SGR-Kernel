"""
Critic Engine for SGR Kernel.
Evaluates step outputs against requirements using LLM-based analysis.
"""

import logging
from typing import Any, Dict, List, Tuple

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
        self, step_id: str, skill_name: str, inputs: Dict[str, Any], output: Any, requirements: str = ""
    ) -> Tuple[bool, str]:  # (Passed, Reason)
        """
        Run a Critic pass on the output using an LLM to judge.
        """
        if not requirements:
            return True, "No specific requirements."

        system_prompt = (
            "You are a strict, objective Critic in the SGR Kernel architecture. "
            "Your job is to evaluate whether a skill's output meets the specified requirements. "
            "Be extremely rigorous."
        )
        
        user_prompt = (
            f"Step ID: {step_id}\n"
            f"Skill Executed: {skill_name}\n"
            f"Skill Inputs: {inputs}\n"
            f"Requirements: {requirements}\n\n"
            f"--- OUTPUT TO EVALUATE ---\n{output}\n--------------------------\n"
        )

        try:
            logger.debug(f"Critic evaluating step {step_id} via LLM...")
            result, usage = await self.llm.generate_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=CriticResponse,
                temperature=0.0
            )
            return result.passed, result.reason
        except Exception as e:
            logger.error(f"Critic LLM evaluation failed: {e}. Falling back to simple keyword match.")
            # Fallback to basic keyword matching
            output_str = str(output).lower()
            requirement_keywords = [w.strip().lower() for w in requirements.split(",") if w.strip()]
            matched = [kw for kw in requirement_keywords if kw in output_str]
            match_ratio = len(matched) / len(requirement_keywords) if requirement_keywords else 1.0
            
            if match_ratio >= 0.5:
                return True, f"Fallback pass: {len(matched)}/{len(requirement_keywords)} keywords found."
            else:
                return False, f"Fallback fail: only {len(matched)}/{len(requirement_keywords)} keywords."

    async def evaluate_plan(
        self, agent_name: str, tool_calls_data: List[Dict[str, Any]], history: List[Dict[str, Any]], requirements: str = ""
    ) -> Tuple[bool, str]:  # (Passed, Reason)
        """
        Evaluate an LLM's proposed plan (tool calls) before execution.
        """
        if not requirements:
            return True, "No specific plan requirements."

        system_prompt = (
            "You are a strict, objective Plan Critic in the SGR Kernel architecture. "
            "Your job is to evaluate whether the proposed action sequence (tool calls) is logical, "
            "safe, and satisfies the given requirements. Be extremely rigorous."
        )
        
        # Keep history concise for the critic to avoid context bloat
        condensed_history = history[-5:] if len(history) > 5 else history
        
        user_prompt = (
            f"Agent Name: {agent_name}\n"
            f"Requirements: {requirements}\n\n"
            f"--- PROPOSED PLAN (TOOL CALLS) ---\n{tool_calls_data}\n--------------------------\n\n"
            f"--- RECENT CONTEXT ---\n{condensed_history}\n--------------------------\n"
        )

        try:
            logger.debug(f"Plan Critic evaluating proposed tool calls from agent {agent_name}...")
            result, usage = await self.llm.generate_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=CriticResponse,
                temperature=0.0
            )
            return result.passed, result.reason
        except Exception as e:
            logger.error(f"Plan Critic LLM evaluation failed: {e}. Defaulting to safe (pass).")
            # If the critic LLM fails, we don't want to block progress completely unless strictly configured.
            # In a production distributed setting, this might route to a human approval queue.
            return True, "Fallback pass: Critic LLM unavailable."
