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


from core.scheduler import Scheduler  # noqa: E402


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
            from core.execution.resolution import resolve_inputs
            from core.scheduler import TaskPayload
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
                            else:
                                # Max attempts reached. Check for Human-in-the-Loop Escalation
                                failure = event.payload.get("failure")
                                failed_type = getattr(failure, "failure_type", None) if failure else None
                                
                                # Only escalate on CRITIC_FAIL (semantic failure), not timeouts or tool crashes
                                if failed_type == "CRITIC_FAIL":
                                    approval_callback = Container.get("approval_callback")
                                    if approval_callback:
                                        logger.warning(f"⏸️ Critic failed {max_attempts} times on step {step_id}. Pausing for human approval.")
                                        
                                        # Publish pause event
                                        pause_event = KernelEvent(
                                            type=EventType.EXECUTION_PAUSED,
                                            request_id=state.request_id,
                                            payload={"step_id": step_id, "reason": "CRITIC_FAIL_ESCALATION"}
                                        )
                                        await self.events.publish(pause_event)
                                        
                                        # Change state to paused
                                        state.status = ExecutionStatus.PAUSED_APPROVAL
                                        
                                        # Invoke callback
                                        # The callback should provide context to the human and return a boolean
                                        context_msg = f"Step '{node.skill_name}' failed critic validation {max_attempts} times.\nReason: {failure.error_message if failure else 'Unknown'}\nApprove partial result?"
                                        is_approved = await approval_callback(context_msg)
                                        
                                        if is_approved:
                                            logger.info(f"✅ Human approved step {step_id} despite Critic failure. Force committing.")
                                            state.status = ExecutionStatus.RUNNING
                                            s_state.status = StepStatus.COMMITTED
                                            # We need to simulate the success so DAG continues
                                            state.skill_outputs[step_id] = s_state.output or "Approved by Human Fallback"
                                        else:
                                            logger.error(f"❌ Human rejected step {step_id}. Aborting execution.")
                                            state.status = ExecutionStatus.ABORTED
                                            break

            # Note: We don't need a wait(FIRST_COMPLETED) here because we are doing wave-based dispatch.
            # This is simpler and less prone to race conditions on the 'state' object.

        # Finalization
        is_success = state.status not in [ExecutionStatus.ABORTED, ExecutionStatus.FAILED]
        
        if is_success:
            await self.events.publish(KernelEvent(type=EventType.EXECUTION_COMPLETED, request_id=state.request_id))

        # Phase 13: Emit Federated Learning Signal
        try:
            from core.learning.federated import global_aggregator, DifferentialPrivacyFilter, LearningPayload
            dp_filter = DifferentialPrivacyFilter(epsilon=1.0)
            
            # Extract basic metric for learning (e.g. how many steps it took to succeed vs fail)
            steps_taken = len(state.step_states)
            raw_payload = LearningPayload(
                agent_id=state.request_id,
                task_type="Orchestrator_DAG",
                success=is_success,
                metrics={"steps_taken": float(steps_taken), "cost_usd": 0.0} # Placeholder
            )
            
            # Apply Differential Privacy locally before sending to central aggregator
            anonymized_payload = dp_filter.anonymize_metrics(raw_payload)
            global_aggregator.receive_payload(anonymized_payload)
            
            await self.events.publish(KernelEvent(
                type=EventType.LEARNING_SIGNAL, 
                request_id=state.request_id,
                payload={"status": "dp_filtered_signal_sent"}
            ))
        except Exception as e:
            logger.warning(f"Failed to emit learning signal: {e}")

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

        summary = "\n".join(results)

        # Phase 11: Automated Root Cause Analysis (RCA)
        if state.status in (ExecutionStatus.ABORTED, ExecutionStatus.FAILED):
            try:
                from core.debugging.causal_analyzer import CausalAnalyzer
                rca = CausalAnalyzer().find_root_cause(state)
                rca_block = (
                    f"\n\n🚨 [AUTOMATED ROOT CAUSE ANALYSIS] 🚨\n"
                    f"Component: {rca.component}\n"
                    f"Reason:    {rca.reason}\n"
                    f"Suggested Fix: {rca.fix_suggestion}\n"
                )
                summary += rca_block
                logger.error(f"Workflow {state.request_id} failed. RCA: {rca.component} -> {rca.reason}")
            except Exception as e:
                logger.warning(f"Failed to generate RCA: {e}")

        return summary
