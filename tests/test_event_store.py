
import pytest

from core.event_store import EventLog
from core.events import EventType, KernelEvent
from core.runtime import CoreEngine


@pytest.mark.asyncio
async def test_event_persistence():
    """
    Verify that an event published to the bus is saved to the DB.
    """
    engine = CoreEngine()
    await engine.init() # Create tables
    
    # Create a test event
    test_event = KernelEvent(
        type=EventType.PLAN_CREATED,
        request_id="test_req_persist",
        payload={"test": "data"}
    )
    
    # Publish
    await engine.events.publish(test_event)
    
    # Check DB directly
    async with engine.db.async_session_factory() as session:
        from sqlalchemy import select
        stmt = select(EventLog).where(EventLog.event_id == test_event.event_id)
        result = await session.execute(stmt)
        log_entry = result.scalar_one_or_none()
        
        assert log_entry is not None, "Event was not persisted to EventLog table"
        assert log_entry.request_id == "test_req_persist"
        assert log_entry.payload == {"test": "data"}
        
    print(f"✅ Event {test_event.event_id} successfully persisted!")
