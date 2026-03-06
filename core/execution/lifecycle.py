import asyncio
import logging
import time
from typing import Any

from core.critic import CriticEngine
from core.events import EventType, KernelEvent
from core.execution import (
    ExecutionState,
    FailureRecord,
    SemanticFailureType,
    StepNode,
    StepStatus,
)
from core.execution.policy import StepResult
from core.governance import GovernanceHooksBus
from core.reliability import ReliabilityEngine
from core.repair import RepairEngine
from core.skill_interface import SkillContext, SkillRuntimeAdapter

logger = logging.getLogger(__name__)

class StepLifecycleEngine:
    """
    RFC v2 Section 3.3: StepLifecycleEngine (Hardened v2).
    Pure logic: performs step phases and returns events. Does NOT mutate state.
    """

    def __init__(
        self,
        skill_adapter: SkillRuntimeAdapter,
        reliability: ReliabilityEngine,
        critic: CriticEngine,
        repair: RepairEngine,
        hooks: GovernanceHooksBus,
    ):
        self.skill_adapter = skill_adapter
        self.reliability = reliability
        self.critic = critic
        self.repair = repair
        self.hooks = hooks

    async def run_step(
        self, step: StepNode, request_id: str, current_outputs: dict[str, Any], attempt: int = 1
    ) -> StepResult:
        """
        Execute a SINGLE attempt of the step lifecycle.
        Returns a StepResult containing events.
        """
        step_id = step.id
        events = []

        # Transition: PENDING -> RUNNING (via Event)
        events.append(
            KernelEvent(
                type=EventType.STEP_STARTED,
                request_id=request_id,
                step_id=step_id,
                payload={"attempt": attempt},
                timestamp=time.time(),
            )
        )

        try:
            logger.debug(f"Executing step {step_id} (Attempt {attempt})")

            # --- Phase 1: EXECUTE ---
            current_tier = self.reliability.get_escalation_tier(attempt - 1)
            skill_config = step.inputs_template.copy()
            skill_config.update({"tier": current_tier})

            # Note: Context now is more restricted
            ctx = SkillContext(
                execution_state=None,  # DO NOT PASS FULL STATE
                llm_service=None,
                tool_registry=self.skill_adapter.registry,
                config=skill_config,
            )
            # In-memory context for outputs
            ctx.step_outputs = current_outputs

            # Execute
            result_obj = await asyncio.wait_for(
                self.skill_adapter.execute_skill(step.skill_name, ctx), timeout=step.timeout_seconds
            )
            result = result_obj.output

            # --- Phase 3: CRITIC ---
            if step.critic_required:
                try:
                    passed, reason = await self.critic.evaluate(step.id, step.skill_name, {}, result)
                    if not passed:
                        raise ValueError(f"Critic Failed: {reason}")
                except Exception as e:
                    # Ensure we classify infrastructure errors in Critic as CRITIC_FAIL
                    if "Critic Failed" in str(e):
                        raise
                    raise ValueError(f"Critic Failed (System Error): {e}") from e

            # --- Phase 6: COMMIT (via Event) ---
            events.append(
                KernelEvent(
                    type=EventType.STEP_COMPLETED,
                    request_id=request_id,
                    step_id=step_id,
                    payload={"output": result},
                    timestamp=time.time(),
                )
            )
            return StepResult(events=events, success=True)

        except Exception as e:
            logger.error(f"Step {step_id} execution failed: {e}", exc_info=True)

            failure_type = self._classify_failure(e)
            fail_rec = FailureRecord(
                step_id=step_id,
                failure_type=failure_type,
                phase=StepStatus.RUNNING,
                error_class=type(e).__name__,
                retryable=True,
                repairable=True,
                error_message=str(e),
            )

            events.append(
                KernelEvent(
                    type=EventType.STEP_FAILED,
                    request_id=request_id,
                    step_id=step_id,
                    payload={"failure": fail_rec},
                    timestamp=time.time(),
                )
            )
            return StepResult(events=events, success=False)

    async def execute_task(self, payload: Any) -> StepResult:
        """
        Execute a task payload (Pre-resolved inputs).
        Used by Scheduler (Local & Remote Workers).
        """
        # Unwrap payload (TaskPayload object)
        step_id = payload.step_id
        request_id = payload.request_id
        attempt = payload.attempt
        inputs = payload.inputs
        skill_name = payload.skill_name
        
        events = []
        
        # Telemetry: Step Start
        events.append(
            KernelEvent(
                type=EventType.STEP_STARTED,
                request_id=request_id,
                step_id=step_id,
                payload={"attempt": attempt},
                timestamp=time.time(),
            )
        )
        
        try:
            # Governance: Before Step
            from core.governance import HOOK_AFTER_STEP, HOOK_BEFORE_STEP
            await self.hooks.emit(HOOK_BEFORE_STEP, payload)

            # Context Setup
            ctx = SkillContext(
                execution_state=None, 
                llm_service=None,
                tool_registry=self.skill_adapter.registry,
                config=inputs, # Direct inputs
            )
            
            timeout = payload.timeout
            
            result_obj = await asyncio.wait_for(
                self.skill_adapter.execute_skill(skill_name, ctx), timeout=timeout
            )
            result = result_obj.output

            # Governance: After Step
            await self.hooks.emit(HOOK_AFTER_STEP, payload, result)

            events.append(
                KernelEvent(
                    type=EventType.STEP_COMPLETED,
                    request_id=request_id,
                    step_id=step_id,
                    payload={"output": result},
                    timestamp=time.time(),
                )
            )
            return StepResult(events=events, success=True)
            
        except Exception as e:
            failure_type = self._classify_failure(e)
            fail_rec = FailureRecord(
                step_id=step_id,
                failure_type=failure_type,
                phase=StepStatus.RUNNING, # Fix enum case if needed
                error_class=type(e).__name__,
                retryable=True,
                repairable=True,
                error_message=str(e),
            )

            events.append(
                KernelEvent(
                    type=EventType.STEP_FAILED,
                    request_id=request_id,
                    step_id=step_id,
                    payload={"failure": fail_rec},
                    timestamp=time.time(),
                )
            )
            return StepResult(events=events, success=False)
            
    def _check_governance(self, step: StepNode, state: ExecutionState):
        if state.token_budget and state.tokens_used >= state.token_budget:
            raise RuntimeError(f"Token Budget Exceeded ({state.tokens_used}/{state.token_budget})")

        skill = self.skill_adapter.registry.get(step.skill_name)
        if skill:
            for cap in skill.capabilities:
                if cap not in step.required_capabilities:
                    raise PermissionError(f"Security Violation: Skill '{step.skill_name}' requires '{cap}'")

    def _classify_failure(self, e: Exception) -> SemanticFailureType:
        msg = str(e).lower()
        if "critic failed" in msg:
            return SemanticFailureType.CRITIC_FAIL
        if "validation" in msg:
            return SemanticFailureType.SCHEMA_FAIL
        if "security violation" in msg:
            return SemanticFailureType.CAPABILITY_VIOLATION
        if "timeout" in msg or isinstance(e, asyncio.TimeoutError):
            return SemanticFailureType.TIMEOUT
        return SemanticFailureType.TOOL_ERROR
