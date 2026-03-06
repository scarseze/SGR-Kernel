from unittest.mock import AsyncMock

import pytest

from core.memory import Message
from core.memory_manager import MemoryManager


@pytest.fixture
def mock_memory():
    mock = AsyncMock()
    # Return more messages than keep_count (which is 5 in memory_manager)
    mock.get_history.return_value = [
        Message(role="user", content="msg 1"),
        Message(role="user", content="msg 2"),
        Message(role="user", content="msg 3"),
        Message(role="user", content="msg 4"),
        Message(role="user", content="msg 5"),
        Message(role="user", content="I changed my mind, I like Python now."),
    ]
    mock.get_last_summary.return_value = "User prefers Java."
    return mock

@pytest.fixture
def mock_summarizer():
    mock = AsyncMock()
    mock.llm = AsyncMock()
    mock.llm.generate.return_value = "YES"
    mock.summarize.return_value = "User prefers Python."
    return mock

@pytest.mark.asyncio
async def test_manage_summarization_with_conflict(mock_memory, mock_summarizer):
    manager = MemoryManager(memory=mock_memory, summarizer=mock_summarizer)
    manager.summary_trigger_threshold = 1  # Force triggering immediately
    
    await manager.manage_summarization("user_123")
    
    # Verify conflict prompt was dispatched to LLM
    assert mock_summarizer.llm.generate.called
    prompt = mock_summarizer.llm.generate.call_args[0][0]
    assert "Does the NEW CONVERSATION contradict or update facts in the PREVIOUS SUMMARY?" in prompt
    assert "User prefers Java" in prompt
    
    # Verify summarization was called with conflict context injected
    assert mock_summarizer.summarize.called
    context_msgs = mock_summarizer.summarize.call_args[0][0]
    assert len(context_msgs) > 0
    # The first injected message should be the system summary with notice
    assert "Notice: Some facts may be contradicted" in context_msgs[0].content

@pytest.mark.asyncio
async def test_manage_summarization_no_conflict(mock_memory, mock_summarizer):
    mock_summarizer.llm.generate.return_value = "NO"
    manager = MemoryManager(memory=mock_memory, summarizer=mock_summarizer)
    manager.summary_trigger_threshold = 1
    
    await manager.manage_summarization("user_123")
    
    # Verify summarization called with normal context instead of conflict notice
    context_msgs = mock_summarizer.summarize.call_args[0][0]
    assert "Notice: Some facts may be contradicted" not in context_msgs[0].content
    assert context_msgs[0].content == "Previous Summary: User prefers Java."
