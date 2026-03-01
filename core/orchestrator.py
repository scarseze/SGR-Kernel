"""
ExecutionOrchestrator for SGR Kernel.
Manages the DAG execution loop via events.
"""

import logging

from core.container import Container
from core.events import EventType, KernelEvent
from core.execution import ExecutionState, ExecutionStatus, StepStatus
from core.execution.graph_engine import ExecutionGraphEngine

logger = logging.getLogger(__name__)


from core.scheduler import Scheduler


class ExecutionOrchestrator:
    """
    Heart of the system. Manages the lifecycle of execution and DAG scheduling.
    Hardened v2: Uses Scheduler and Centralized Event Application.
    """

    def __init__(self):
        self.events = Container.get("event_bus")
        self.lifecycle = Container.get("lifecycle")
        self.scheduler = Scheduler()

    async def execute(self, state: ExecutionState) -> str:
        """
        Core DAG Execution Loop (Hardened v2).
        """
        # Publish Execution Started
        await self.events.publish(KernelEvent(type=EventType.EXECUTION_STARTED, request_id=state.request_id))

        if state.plan_ir and state.plan_ir.direct_response:
             await self.events.publish(KernelEvent(type=EventType.EXECUTION_COMPLETED, request_id=state.request_id))
             return state.plan_ir.direct_response

        graph_engine = ExecutionGraphEngine(state)

        while not graph_engine.is_complete():
            if state.status == ExecutionStatus.ABORTED:
                break

            # 1. Get Runnable Steps (Wave)
            runnable = graph_engine.get_runnable_steps()
            if not runnable and not graph_engine.is_complete():
                logger.error(f"Deadlock detected in {state.request_id}")
                break

            if not runnable:
                break

            # 2. Dispatch Wave
            from core.scheduler import TaskPayload
            from core.execution.resolution import resolve_inputs
            from core.tracing import get_trace_context
            
            tasks = []
            trace_ctx = get_trace_context()
            
            for step in runnable:
                s_state = state.step_states.get(step.id)
                attempt = (s_state.attempts if s_state else 0) + 1
                
                # Resolve Inputs (Phase 5)
                # Orchestrator does resolution logic so Scheduler/Worker is dumb
                resolved_inputs = resolve_inputs(step.inputs_template, state.skill_outputs)
                
                payload = TaskPayload(
                    step_id=step.id,
                    skill_name=step.skill_name,
                    inputs=resolved_inputs,
                    request_id=state.request_id,
                    attempt=attempt,
                    trace_context=trace_ctx,
                    timeout=step.timeout_seconds
                )
                
                # Deduplication / Idempotency Guard
                # Attempt to get a Redis lock for this execution step. Ensures exactly-once business logic execution.
                if hasattr(self.scheduler, 'redis') and self.scheduler.redis:
                    dedup_key = f"sgr:exec:{state.request_id}:{step.id}"
                    if not self.scheduler.redis.setnx(dedup_key, "1"):
                        logger.warning(f"🚫 Deduplication: Step {step.id} is already executing or completed. Skiping.")
                        # Emit a failed event to unlock the DAG
                        dup_event = KernelEvent(
                            type=EventType.STEP_FAILED,
                            request_id=state.request_id,
                            step_id=step.id,
                            payload={"error": "409 Conflict: Duplicate Execution Blocked"}
                        )
                        await self.events.publish(dup_event)
                        continue
                    # Lock expires after somewhat longer than the task timeout to cleanly prevent duplicates without holding forever
                    self.scheduler.redis.expire(dedup_key, int(step.timeout_seconds) + 60)

                tasks.append(payload)

            results = await self.scheduler.dispatch(tasks)

            # 3. Centralized Event Application
            for result in results:
                for event in result.events:
                    # Publish triggers StateManager.apply via global subscriber in CoreEngine
                    await self.events.publish(event)

                # 4. Retry Logic
                if not result.success:
                    # Resolve step from results
                    # (Quick hack: find which step in 'results' failed)
                    # This is slightly inefficient but works for now
                    for event in result.events:
                        if event.type == EventType.STEP_FAILED:
                            step_id = event.step_id
                            s_state = state.step_states.get(step_id)
                            node = graph_engine.steps_lut.get(step_id)
                            
                            max_attempts = 1
                            if node and hasattr(node, "retry_policy") and node.retry_policy:
                                max_attempts = getattr(node.retry_policy, "max_attempts", 3)
                                
                            if s_state.attempts < max_attempts:
                                # Idempotency Guard (Phase 5)
                                # Only block automatic retries for non-idempotent steps that have
                                # ALREADY COMMITTED side effects (i.e. reached COMMITTED status before failing).
                                # Steps that failed during RUNNING phase haven't committed anything,
                                # so retrying them is safe regardless of idempotency flag.
                                failure = event.payload.get("failure")
                                failed_phase = getattr(failure, "phase", "RUNNING") if failure else "RUNNING"
                                if not node.idempotent and s_state.attempts >= 1 and failed_phase not in ("RUNNING", StepStatus.RUNNING):
                                    logger.warning(f"🚫 Blocking retry for non-idempotent step {step_id} (failed in {failed_phase})")
                                    continue

                                logger.info(f"🔄 Retrying step {step_id} (Attempt {s_state.attempts}/{max_attempts})")
                                retry_event = KernelEvent(
                                    type=EventType.STEP_RETRYING,
                                    request_id=state.request_id,
                                    step_id=step_id,
                                    payload={"reason": "Automatic Retry"}
                                )
                                await self.events.publish(retry_event)

            # Note: We don't need a wait(FIRST_COMPLETED) here because we are doing wave-based dispatch.
            # This is simpler and less prone to race conditions on the 'state' object.

        # Finalization
        if state.status not in [ExecutionStatus.ABORTED, ExecutionStatus.FAILED]:
            await self.events.publish(KernelEvent(type=EventType.EXECUTION_COMPLETED, request_id=state.request_id))

        return self._summarize_result(state)

    def _summarize_result(self, state: ExecutionState) -> str:
        if state.plan_ir and state.plan_ir.direct_response:
             return state.plan_ir.direct_response
             
        if not state.step_states:
            return f"No steps executed. Input: {state.input_payload}"

        results = []
        from core.execution import StepStatus
        # Sort by completion time or ID
        sorted_steps = sorted(state.step_states.keys())
        for step_id in sorted_steps:
            s_state = state.step_states[step_id]
            if s_state.status == StepStatus.FAILED and s_state.failure:
                output = f"FAILED: {s_state.failure.error_message}"
            else:
                output = state.skill_outputs.get(step_id, "N/A")
            results.append(f"Step {step_id}: {output}")
        return "\n".join(results)
