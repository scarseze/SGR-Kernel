from typing import Any

"""
StateManager for SGR Kernel.
Handles state transitions via events.
"""

import logging
from typing import List, Optional

from core.events import EventType, KernelEvent
from core.execution import ExecutionState, ExecutionStatus, StepStatus

logger = logging.getLogger(__name__)


class StateManager:
    """
    Central logic for applying events to the ExecutionState.
    Ensures deterministic state transitions.
    """

    @staticmethod
    def apply_event(state: ExecutionState, event: KernelEvent):
        """
        Mutates the state based on the event.
        Logic is strictly derived from event type and payload.
        """
        if event.event_id in state.processed_event_ids:
            logger.warning(f"⚠️ Skipping duplicate event {event.event_id} (Idempotency Check)")
            return

        # Append to audit log
        state.event_log.append(event)
        state.processed_event_ids.add(event.event_id)
        state.updated_at = event.timestamp

        payload = event.payload

        if event.type == EventType.PLAN_CREATED:
            plan_data = payload.get("plan_ir")
            if isinstance(plan_data, dict):
                from core.execution import PlanIR

                state.plan_ir = PlanIR.model_validate(plan_data)
            else:
                state.plan_ir = plan_data

            state.plan_id = state.plan_ir.id if state.plan_ir else None
            state.status = ExecutionStatus.PLANNED
            # Initialize steps
            if state.plan_ir:
                for step in state.plan_ir.steps:
                    state.initialize_step(step.id)

        elif event.type == EventType.EXECUTION_STARTED:
            state.status = ExecutionStatus.RUNNING

        elif event.type == EventType.STEP_STARTED:
            step_id = event.step_id
            if step_id and step_id in state.step_states:
                s_state = state.step_states[step_id]
                s_state.status = StepStatus.RUNNING
                s_state.started_at = event.timestamp
                s_state.attempts = payload.get("attempt", s_state.attempts)

        elif event.type == EventType.STEP_COMPLETED:
            step_id = event.step_id
            if step_id and step_id in state.step_states:
                s_state = state.step_states[step_id]
                s_state.status = StepStatus.COMMITTED
                s_state.finished_at = event.timestamp
                s_state.output = payload.get("output")
                # Also update flat map for easy access
                state.skill_outputs[step_id] = s_state.output

        elif event.type == EventType.STEP_FAILED:
            step_id = event.step_id
            if step_id and step_id in state.step_states:
                s_state = state.step_states[step_id]
                s_state.status = StepStatus.FAILED
                s_state.finished_at = event.timestamp
                if "failure" in payload:
                    s_state.failure = payload["failure"]

        elif event.type == EventType.STEP_RETRYING:
            step_id = event.step_id
            if step_id and step_id in state.step_states:
                s_state = state.step_states[step_id]
                s_state.status = StepStatus.PENDING
                s_state.finished_at = None
                # Attempt count will be incremented by next STEP_STARTED

        elif event.type == EventType.EXECUTION_COMPLETED:
            state.status = ExecutionStatus.COMPLETED

        elif event.type == EventType.EXECUTION_FAILED:
            state.status = ExecutionStatus.FAILED

        elif event.type == EventType.EXECUTION_ABORTED:
            state.status = ExecutionStatus.ABORTED

        elif event.type == EventType.TELEMETRY_RECORDED:
            # We could update budgets here if telemetry includes them
            pass

        logger.debug(f"Applied event {event.type} to state {state.request_id}")

    @classmethod
    def reconstruct(cls, events: List[KernelEvent], request_id: Optional[str] = None) -> ExecutionState:
        """
        Reconstructs the ExecutionState by replaying a sequence of events.
        """
        if not events:
            raise ValueError("No events provided for reconstruction.")

        # 1. Find the first relevant Event to determine request_id if not provided
        rid = request_id or events[0].request_id

        # 2. Initialize empty state
        state = ExecutionState(request_id=rid, input_payload="")

        # 3. Sort events by timestamp (if not already sorted)
        sorted_events = sorted(events, key=lambda e: e.timestamp)

        # 4. Apply each event
        for event in sorted_events:
            if event.request_id == rid:
                cls.apply_event(state, event)

        return state

    @staticmethod
    def snapshot(state: ExecutionState) -> bytes:
        """Serialize state for checkpointing."""
        return state.json().encode("utf-8")
