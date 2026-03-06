import pytest
import datetime
from unittest.mock import AsyncMock, MagicMock
from core.memory import PersistentMemory

@pytest.fixture
def mock_vector_store():
    store = AsyncMock()
    return store

@pytest.fixture
def memory(mock_vector_store):
    db_mock = AsyncMock()
    return PersistentMemory(db=db_mock, vector_store=mock_vector_store)

@pytest.mark.asyncio
async def test_apply_time_decay(memory, mock_vector_store):
    result = await memory.apply_time_decay(older_than_days=30)
    
    # Verify the vector store delete method was called
    assert result is True
    assert mock_vector_store.delete_by_payload_filter.called
    
    # Check arguments
    kwargs = mock_vector_store.delete_by_payload_filter.call_args.kwargs
    assert kwargs["collection"] == memory.collection_name
    assert kwargs["key"] == "timestamp"
    
    # Validate the passed ISO timestamp is around 30 days ago
    cutoff_iso = kwargs["value_lt"]
    cutoff_date = datetime.datetime.fromisoformat(cutoff_iso)
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    delta = now_utc - cutoff_date
    assert 29 < delta.days < 31

@pytest.mark.asyncio
async def test_apply_time_decay_no_vector_store():
    mem = PersistentMemory(db=AsyncMock(), vector_store=None)
    result = await mem.apply_time_decay(30)
    assert result is False
