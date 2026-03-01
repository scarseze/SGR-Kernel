"""
KernelEvent definitions for SGR Kernel.
"""

import time
import uuid
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class EventType(str, Enum):
    # Lifecycle Events
    PLAN_CREATED = "PLAN_CREATED"
    EXECUTION_STARTED = "EXECUTION_STARTED"
    EXECUTION_COMPLETED = "EXECUTION_COMPLETED"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    EXECUTION_ABORTED = "EXECUTION_ABORTED"

    # Step Events
    STEP_SCHEDULED = "STEP_SCHEDULED"
    STEP_STARTED = "STEP_STARTED"
    STEP_COMPLETED = "STEP_COMPLETED"
    STEP_FAILED = "STEP_FAILED"
    STEP_RETRYING = "STEP_RETRYING"
    STEP_VALIDATING = "STEP_VALIDATING"

    # Resource Events
    CHECKPOINT_SAVED = "CHECKPOINT_SAVED"
    TELEMETRY_RECORDED = "TELEMETRY_RECORDED"


class KernelEvent(BaseModel):
    """
    Standard event structure for the Kernel.
    """

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: EventType
    payload: Dict[str, Any] = Field(default_factory=dict)
    request_id: str
    timestamp: float = Field(default_factory=time.time)

    # Metadata for replay/trace
    step_id: Optional[str] = None
    actor: str = "kernel"
