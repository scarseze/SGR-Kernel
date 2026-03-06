import datetime
import json
from unittest.mock import AsyncMock, patch

import pytest

from core.container import Container
from core.reconciler import BackgroundReconciler
from core.ui_memory import UIMemory


@pytest.mark.asyncio
async def test_ui_memory_reflection(tmp_path):
    """
    Tests that a session with many messages can be fetched and compressed 
    by the Reflection worker methods.
    """
    db_path = tmp_path / "test_memory.sqlite"
    db_url = f"sqlite+aiosqlite:///{db_path}"
    
    memory = UIMemory(db_url=db_url)
    await memory.initialize()
    
    # 1. Insert a mock session with 20 dummy messages manually, with an old timestamp
    session_id = "test_reflection_session_1"
    
    history = [
        {"role": "system", "content": "You are a helpful AI"}
    ]
    for i in range(20):
        history.append({"role": "user", "content": f"Message {i}"})
        history.append({"role": "assistant", "content": f"Reply {i}"})
        
    # We want it to be "old" enough to be picked up
    now = datetime.datetime.now(datetime.timezone.utc)
    old_time = now - datetime.timedelta(hours=2)
    
    history_json = json.dumps(history)
    
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    stmt = sqlite_insert(memory.sessions).values(
        session_id=session_id,
        org_id="default_org",
        history_json=history_json,
        active_agent_name="RouterAgent",
        transfer_count=0,
        created_at=old_time,
        updated_at=old_time
    )
    async with memory.engine.begin() as conn:
        await conn.execute(stmt)
        
    # 2. Test get_unreflected_sessions
    unreflected = await memory.get_unreflected_sessions(limit=5, inactive_hours=1)
    assert len(unreflected) == 1
    assert unreflected[0]["session_id"] == session_id
    assert len(unreflected[0]["history"]) == 41 # 1 system + 20 pairs
    
    # 3. Test reflect_session
    # Mock the LLM summarize_history call to avoid actual API request
    with patch.object(memory, 'summarize_history', new_callable=AsyncMock) as mock_summarize:
        mock_summarize.return_value = "Compacted summary of 41 messages."
        
        success = await memory.reflect_session(session_id, unreflected[0]["history"])
        assert success is True
        
        # Verify it was updated in DB
        loaded_history, _, _ = await memory.load_session(session_id)
        
        # Should now be System + Summary + remaining elements up to max_messages (10)
        assert len(loaded_history) <= 12 
        assert "[AUTO-SUMMARY OF PREVIOUS CONTEXT]" in loaded_history[1]["content"]

@pytest.mark.asyncio
async def test_reconciler_reflect_old_memories():
    mock_memory = AsyncMock()
    mock_memory.get_unreflected_sessions.return_value = [
        {"session_id": "sess_1", "org_id": "org_1", "history": [{"role": "user", "content": "hi"} for _ in range(20)]}
    ]
    mock_memory.reflect_session.return_value = True

    Container.register("ui_memory", mock_memory)
    
    reconciler = BackgroundReconciler()
    await reconciler._reflect_old_memories()
    
    mock_memory.get_unreflected_sessions.assert_called_once()
    mock_memory.reflect_session.assert_called_once()
