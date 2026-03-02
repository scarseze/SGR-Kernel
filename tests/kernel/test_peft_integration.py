import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from core.agent import Agent
from core.swarm import SwarmEngine


def _make_stream_chunks(content: str, tool_calls=None):
    """Create a list of mock streaming chunks that litellm.stream_chunk_builder can process."""
    chunk = MagicMock()
    chunk.choices = [MagicMock()]
    chunk.choices[0].delta.content = content
    chunk.choices[0].delta.tool_calls = tool_calls
    chunk.choices[0].delta.role = "assistant"
    return [chunk]


def _make_built_response(content: str, tool_calls=None):
    """Create what litellm.stream_chunk_builder returns after processing chunks."""
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = content
    response.choices[0].message.tool_calls = tool_calls
    response.usage.total_tokens = 10
    return response


async def _fake_stream(*args, **kwargs):
    """Simulate an async generator returned by _safe_call_llm with stream=True."""
    chunk = MagicMock()
    chunk.choices = [MagicMock()]
    chunk.choices[0].delta.content = "SELECT * FROM users;"
    chunk.choices[0].delta.tool_calls = None
    chunk.choices[0].delta.role = "assistant"
    yield chunk


@pytest.mark.asyncio
async def test_peft_lora_adapter_injection():
    """Verify that SwarmEngine injects the Agent's lora_adapter into LiteLLM completion args."""
    
    agent = Agent(
        name="sql_expert",
        instructions="You write SQL.",
        lora_adapter="sql-lora-v1"
    )
    
    with patch("core.swarm.Container") as mock_container:
        mock_container.get.return_value = None
        engine = SwarmEngine(llm_config={"model": "test-model"})
    
    built_response = _make_built_response("SELECT * FROM users;")
    
    with patch.object(engine, "_safe_call_llm", side_effect=_fake_stream) as mock_llm, \
         patch("core.swarm.litellm.stream_chunk_builder", return_value=built_response), \
         patch("core.swarm.litellm.completion_cost", return_value=0.0):
        
        await engine.execute(
            starting_agent=agent,
            messages=[{"role": "user", "content": "Query users table"}]
        )
        
        # Assert _safe_call_llm was called with extra_body containing lora_name
        mock_llm.assert_called_once()
        call_kwargs = mock_llm.call_args.kwargs
        
        assert "extra_body" in call_kwargs, "extra_body missing from litellm call"
        assert call_kwargs["extra_body"] == {"lora_name": "sql-lora-v1"}


async def _fake_stream_hello(*args, **kwargs):
    """Simulate an async generator for the no-adapter test."""
    chunk = MagicMock()
    chunk.choices = [MagicMock()]
    chunk.choices[0].delta.content = "Hello there."
    chunk.choices[0].delta.tool_calls = None
    chunk.choices[0].delta.role = "assistant"
    yield chunk


@pytest.mark.asyncio
async def test_no_peft_lora_adapter_injection():
    """Verify that SwarmEngine doesn't inject extra_body if no lora_adapter is specified."""
    
    agent = Agent(
        name="generalist",
        instructions="You are helpful."
    )
    
    with patch("core.swarm.Container") as mock_container:
        mock_container.get.return_value = None
        engine = SwarmEngine(llm_config={"model": "test-model"})
    
    built_response = _make_built_response("Hello there.")
    
    with patch.object(engine, "_safe_call_llm", side_effect=_fake_stream_hello) as mock_llm, \
         patch("core.swarm.litellm.stream_chunk_builder", return_value=built_response), \
         patch("core.swarm.litellm.completion_cost", return_value=0.0):
        
        await engine.execute(
            starting_agent=agent,
            messages=[{"role": "user", "content": "Hi"}]
        )
        
        mock_llm.assert_called_once()
        call_kwargs = mock_llm.call_args.kwargs
        
        # extra_body should not be present (or at least not contain lora_name)
        assert "extra_body" not in call_kwargs or "lora_name" not in call_kwargs.get("extra_body", {})
