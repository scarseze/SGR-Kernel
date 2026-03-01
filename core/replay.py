from typing import List, Optional

from core.events import KernelEvent
from core.execution import ExecutionState
from core.state_manager import StateManager


class ReplayEngine:
    """
    Handles state reconstruction and forking (time-travel).
    """

    @staticmethod
    def replay(events: List[KernelEvent], up_to_event_id: Optional[str] = None) -> ExecutionState:
        """
        Reconstructs state from a list of events.
        """
        if up_to_event_id:
            truncated = []
            for e in events:
                truncated.append(e)
                if e.event_id == up_to_event_id:
                    break
            events = truncated

        return StateManager.reconstruct(events)

    @staticmethod
    def fork(events: List[KernelEvent], from_event_id: str) -> ExecutionState:
        """
        Creates a new state fork from a specific point in history.
        """
        state = ReplayEngine.replay(events, up_to_event_id=from_event_id)
        # In a real system, we might change the request_id to mark it as a fork
        state.request_id = f"{state.request_id}-fork-{int(state.updated_at)}"
        return state
