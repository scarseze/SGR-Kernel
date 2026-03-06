from __future__ import annotations

from enum import Enum
from typing import List

from pydantic import BaseModel

from core.events import KernelEvent
from core.execution import RetryPolicy, SemanticFailureType


class RecoveryAction(str, Enum):
    RETRY = "RETRY"
    REPAIR = "REPAIR"
    IGNORE = "IGNORE"
    ABORT = "ABORT"


class StepResult(BaseModel):
    """Container for events produced by a step execution."""

    events: List[KernelEvent] = []
    success: bool = True


class ExecutionPolicy:
    """
    Decides the next action based on failure events.
    Pure logic, no side effects.
    """

    @staticmethod
    def decide(policy: RetryPolicy, failure_type: SemanticFailureType, attempts: int) -> RecoveryAction:
        if attempts >= policy.max_attempts:
            return RecoveryAction.ABORT

        if failure_type == SemanticFailureType.TIMEOUT:
            return RecoveryAction.RETRY

        if failure_type in [SemanticFailureType.SCHEMA_FAIL, SemanticFailureType.CRITIC_FAIL]:
            return RecoveryAction.REPAIR

        if failure_type == SemanticFailureType.CAPABILITY_VIOLATION:
            return RecoveryAction.ABORT

        return RecoveryAction.RETRY
