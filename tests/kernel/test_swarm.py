import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from core.swarm import SwarmEngine
from core.agent import Agent
from skills.base import BaseSkill
from pydantic import BaseModel

class FakeMessage:
    def __init__(self, content, role="assistant", tool_calls=None):
        self.role = role
        self.content = content
        self.tool_calls = tool_calls
    
    def model_dump(self, *args, **kwargs):
        return {
            "role": self.role,
            "content": self.content,
            "tool_calls": [{"id": tc.id, "function": {"name": tc.function.name, "arguments": tc.function.arguments}} for tc in self.tool_calls] if self.tool_calls else None
        }

class FakeChoice:
    def __init__(self, message):
        self.message = message

class FakeDelta:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls

class FakeChunkChoice:
    def __init__(self, delta):
        self.delta = delta

class FakeChunk:
    def __init__(self, delta):
        self.choices = [FakeChunkChoice(delta)]

class FakeResponse:
    def __init__(self, message):
        self.choices = [FakeChoice(message)]
        self.usage = MagicMock(total_tokens=10)

def create_async_chunk_generator(chunks):
    async def async_gen():
        for chunk in chunks:
            yield chunk
    return async_gen()

# Mock Skill and Schema
class MockSkillSchema(BaseModel):
    action: str

class MockSkill(BaseSkill[MockSkillSchema]):
    def __init__(self, name, requirements=None):
        self._name = name
        self._requirements = requirements
    
    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return "A mock skill"

    @property
    def requirements(self) -> str:
        return self._requirements

    @property
    def input_schema(self):
        return MockSkillSchema
    
    @property
    def metadata(self):
        return None

    def execute(self, params):
        return f"Executed {params.action}"

@pytest.fixture
def test_agent():
    skill = MockSkill("test_tool", requirements="Must be successful")
    return Agent(
        name="TestAgent",
        instructions="You are a test agent.",
        skills=[skill]
    )

@pytest.mark.asyncio
@patch('core.swarm.litellm.completion_cost', return_value=0.0)
@patch('core.swarm.litellm.stream_chunk_builder')
@patch('core.swarm.SwarmEngine._safe_call_llm', new_callable=AsyncMock)
async def test_swarm_context_guardian_token_limit_triggered(mock_safe_call_llm, mock_stream_builder, mock_cost, test_agent):
    mock_swarm_engine = SwarmEngine(llm_config={"model": "test-model", "max_context_tokens": 100})
    # Create fake history that exceeds (100 * 0.8) = 80 tokens 
    # approx_tokens = sum(len(str)) // 4
    # To get > 80 tokens, we need > 320 characters in history
    long_content = "A" * 350 
    history = [
        {"role": "user", "content": "Start"},
        {"role": "assistant", "content": long_content},
        {"role": "user", "content": "End"}
    ]
    
    summary_mock_response = FakeResponse(FakeMessage(content="Summarized context"))
    no_tool_call_response = FakeResponse(FakeMessage(content="Done"))
    
    # Needs to return summary for the summarization call (stream=False), and a dummy iterable for stream=True
    def llm_side_effect(*args, **kwargs):
        if kwargs.get("stream"):
            return create_async_chunk_generator([MagicMock(choices=None)])
        return summary_mock_response
        
    mock_safe_call_llm.side_effect = llm_side_effect
    mock_stream_builder.return_value = no_tool_call_response

    res, agent, transfers = await mock_swarm_engine.execute(
        starting_agent=test_agent,
        messages=history,
        max_turns=1
    )
    
    assert res == "Done"
    # The LLM should have been called twice: 1 for summary (stream=False, explicit internal call) 
    # and 1 for actual turn (stream=True)
    assert mock_safe_call_llm.call_count == 2
    
    # Check that summary was requested
    summary_call_args = mock_safe_call_llm.call_args_list[0]
    called_messages = summary_call_args.kwargs["messages"]
    assert any("Summarize the following" in m["content"] for m in called_messages if m["role"] == "user")

@pytest.mark.asyncio
@patch('core.swarm.litellm.completion_cost', return_value=0.0)
@patch('core.swarm.litellm.stream_chunk_builder')
@patch('core.swarm.SwarmEngine._safe_call_llm', new_callable=AsyncMock)
async def test_swarm_multi_turn_critic(mock_safe_call_llm, mock_stream_builder, mock_cost, test_agent):
    """
    Tests Agentic Reasoning (Critic Loop).
    The agent calls a tool. The Critic rejects it.
    The agent automatically retries internally based on the rejection feedback.
    The Critic accepts the second attempt.
    """
    mock_critic = AsyncMock()
    # Turn 1: Critic says False. Turn 2: Critic says True
    mock_critic.evaluate.side_effect = [(False, "Output is poorly formatted"), (True, "Looks good")]
    
    mock_swarm_engine = SwarmEngine(llm_config={"model": "test-model"})
    
    # 1. First llm call returns a tool call
    fake_tool_call_1 = MagicMock()
    fake_tool_call_1.id = "call_1"
    fake_tool_call_1.function.name = "test_tool"
    fake_tool_call_1.function.arguments = '{"action": "attempt_1"}'
    response_turn_1 = FakeResponse(FakeMessage(content=None, tool_calls=[fake_tool_call_1]))
    
    # 2. Second llm call returns another tool call (the retry)
    fake_tool_call_2 = MagicMock()
    fake_tool_call_2.id = "call_2"
    fake_tool_call_2.function.name = "test_tool"
    fake_tool_call_2.function.arguments = '{"action": "attempt_2"}'
    response_turn_2 = FakeResponse(FakeMessage(content=None, tool_calls=[fake_tool_call_2]))
    
    # 3. Third llm call returns final success message
    response_final = FakeResponse(FakeMessage(content="Task completed successfully after retry."))

    # Setup the stream chunk builder to yield the responses sequentially
    mock_stream_builder.side_effect = [response_turn_1, response_turn_2, response_final]
    
    mock_execute = MagicMock(return_value="executed_mock")
    test_agent.skills[0].execute = mock_execute

    # The actual async network call is just yielding dummy stream chunks
    def llm_side_effect(*args, **kwargs):
        return create_async_chunk_generator([MagicMock(choices=None)])
    mock_safe_call_llm.side_effect = llm_side_effect

    res, agent, transfers = await mock_swarm_engine.execute(
        starting_agent=test_agent,
        messages=[{"role": "user", "content": "Do a task."}],
        max_turns=5,
        critic_engine=mock_critic
    )

    # Assertions
    assert res == "Task completed successfully after retry."
    
    # The Critic evaluated 2 tool outputs (rejected first, accepted second)
    assert mock_critic.evaluate.call_count == 2
    
    # Verify the inputs the Critic saw
    critic_calls = mock_critic.evaluate.call_args_list
    assert len(critic_calls) == 2
    assert critic_calls[0].kwargs['inputs'] == {'action': 'attempt_1'}
    assert critic_calls[1].kwargs['inputs'] == {'action': 'attempt_2'}
