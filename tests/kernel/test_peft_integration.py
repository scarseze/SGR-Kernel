import pytest
import asyncio
from unittest.mock import patch, MagicMock
from core.agent import Agent
from core.swarm import SwarmEngine

@pytest.mark.asyncio
async def test_peft_lora_adapter_injection():
    """Verify that SwarmEngine injects the Agent's lora_adapter into LiteLLM completion args."""
    
    # 1. Create an agent with a specific LoRA adapter
    agent = Agent(
        name="sql_expert",
        instructions="You write SQL.",
        lora_adapter="sql-lora-v1"
    )
    
    # 2. Setup SwarmEngine with mocked litellm and Container
    with patch("core.swarm.Container") as mock_container:
        # Mock get to return None so QuotaManager is not initialized checking for redis
        mock_container.get.return_value = None
        engine = SwarmEngine(llm_config={"model": "test-model"})
    
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "SELECT * FROM users;"
    mock_response.choices[0].message.tool_calls = None
    mock_response.usage.total_tokens = 10
    
    with patch("core.swarm.litellm.acompletion", return_value=mock_response) as mock_acompletion:
        await engine.execute(
            starting_agent=agent,
            messages=[{"role": "user", "content": "Query users table"}]
        )
        
        # 3. Assert acompletion was called with `extra_body` containing `lora_name`
        mock_acompletion.assert_called_once()
        call_kwargs = mock_acompletion.call_args.kwargs
        
        assert "extra_body" in call_kwargs, "extra_body missing from litellm call"
        assert call_kwargs["extra_body"] == {"lora_name": "sql-lora-v1"}

@pytest.mark.asyncio
async def test_no_peft_lora_adapter_injection():
    """Verify that SwarmEngine doesn't inject extra_body if no lora_adapter is specified."""
    
    # 1. Create a generic agent without a LoRA adapter
    agent = Agent(
        name="generalist",
        instructions="You are helpful."
        # lora_adapter is None by default
    )
    
    with patch("core.swarm.Container") as mock_container:
        mock_container.get.return_value = None
        engine = SwarmEngine(llm_config={"model": "test-model"})
    
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Hello there."
    mock_response.choices[0].message.tool_calls = None
    mock_response.usage.total_tokens = 10
    
    with patch("core.swarm.litellm.acompletion", return_value=mock_response) as mock_acompletion:
        await engine.execute(
            starting_agent=agent,
            messages=[{"role": "user", "content": "Hi"}]
        )
        
        mock_acompletion.assert_called_once()
        call_kwargs = mock_acompletion.call_args.kwargs
        
        # extra_body should not be present (or at least not contain lora_name)
        assert "extra_body" not in call_kwargs or "lora_name" not in call_kwargs.get("extra_body", {})
