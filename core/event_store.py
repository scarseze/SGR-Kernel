import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import Column, String, DateTime, JSON, Integer, Text, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import Base
from core.events import KernelEvent, EventType

logger = logging.getLogger(__name__)


class EventLog(Base):
    """
    Immutable Append-Only Log of all Kernel Events.
    This is the Canonical Source of Truth for the system.
    """
    __tablename__ = "event_log"

    id = Column(Integer, primary_key=True, autoincrement=True)  # Global Sequence ID
    event_id = Column(String, unique=True, index=True, nullable=False)
    request_id = Column(String, index=True, nullable=False)
    event_type = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Trace Context (Phase 5 Observability)
    trace_id = Column(String, nullable=True)
    span_id = Column(String, nullable=True)

    def to_kernel_event(self) -> KernelEvent:
        return KernelEvent(
            id=self.event_id,
            request_id=self.request_id,
            type=EventType(self.event_type),
            payload=self.payload,
            created_at=self.created_at
        )


class EventStore:
    """
    Repository for the Canonical Event Log.
    """
    def __init__(self, session_factory):
        self.session_factory = session_factory

    async def append(self, event: KernelEvent, trace_ctx: dict = None):
        """
        Persist an event to the append-only log.
        """
        trace_ctx = trace_ctx or {}
        async with self.session_factory() as session:
            async with session.begin():
                log_entry = EventLog(
                    event_id=event.event_id, 
                    request_id=event.request_id,
                    event_type=event.type.value,
                    payload=event.model_dump(mode="json").get("payload", {}),
                    created_at=datetime.fromtimestamp(event.timestamp, timezone.utc),
                    trace_id=trace_ctx.get("trace_id"),
                    span_id=trace_ctx.get("span_id")
                )
                session.add(log_entry)
                # Commit happens automatically with session.begin() context

    async def get_by_request(self, request_id: str) -> List[KernelEvent]:
        """
        Retrieve full event stream for a request (Replay support).
        """
        async with self.session_factory() as session:
            stmt = select(EventLog).where(EventLog.request_id == request_id).order_by(EventLog.id)
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [row.to_kernel_event() for row in rows]

    async def get_events_after(self, last_sequence_id: int, limit: int = 100) -> List[EventLog]:
        """
        Support function for Catch-Up Subscriptions or Projections.
        """
        async with self.session_factory() as session:
            stmt = select(EventLog).where(EventLog.id > last_sequence_id).order_by(EventLog.id).limit(limit)
            result = await session.execute(stmt)
            return result.scalars().all()
