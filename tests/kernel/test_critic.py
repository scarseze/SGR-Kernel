from unittest.mock import AsyncMock, MagicMock

import pytest

from core.critic import CriticEngine


@pytest.fixture
def mock_llm():
    return AsyncMock()

@pytest.fixture
def critic(mock_llm):
    return CriticEngine(llm_service=mock_llm)

@pytest.mark.asyncio
async def test_critic_evaluate_no_requirements(critic):
    passed, reason = await critic.evaluate(
        step_id="123", skill_name="test_skill", inputs={}, output="some output", requirements=""
    )
    assert passed is True
    assert reason == "No specific requirements."
    critic.llm.generate_structured.assert_not_called()

@pytest.mark.asyncio
async def test_critic_evaluate_llm_pass(critic, mock_llm):
    # Setup mock to return a passing CriticResponse
    mock_response = MagicMock()
    mock_response.passed = True
    mock_response.reason = "Looks good"
    
    mock_llm.generate_structured.return_value = (mock_response, {"total_tokens": 10})

    passed, reason = await critic.evaluate(
        step_id="123", 
        skill_name="test_skill", 
        inputs={"data": "test"}, 
        output="The file was created successfully.", 
        requirements="Must confirm file creation."
    )
    
    assert passed is True
    assert reason == "Looks good"
    mock_llm.generate_structured.assert_called_once()
    args, kwargs = mock_llm.generate_structured.call_args
    assert "Must confirm file creation" in kwargs["user_prompt"]
    assert "The file was created successfully." in kwargs["user_prompt"]

@pytest.mark.asyncio
async def test_critic_evaluate_llm_fail(critic, mock_llm):
    # Setup mock to return a failing CriticResponse
    mock_response = MagicMock()
    mock_response.passed = False
    mock_response.reason = "Missing confirmation."
    
    mock_llm.generate_structured.return_value = (mock_response, {"total_tokens": 10})

    passed, reason = await critic.evaluate(
        step_id="123", 
        skill_name="test_skill", 
        inputs={}, 
        output="Done.", 
        requirements="Must confirm file creation."
    )
    
    assert passed is False
    assert reason == "Missing confirmation."

@pytest.mark.asyncio
async def test_critic_evaluate_fallback_pass(critic, mock_llm):
    # Make the LLM call throw an exception to trigger the fallback
    mock_llm.generate_structured.side_effect = Exception("API Error")

    passed, reason = await critic.evaluate(
        step_id="123", 
        skill_name="test", 
        inputs={}, 
        output="Success confirmation status", 
        requirements="success, confirmation"
    )
    
    assert passed is True
    assert "Fallback pass" in reason

@pytest.mark.asyncio
async def test_critic_evaluate_fallback_fail(critic, mock_llm):
    # Make the LLM call throw an exception to trigger the fallback
    mock_llm.generate_structured.side_effect = Exception("API Error")

    passed, reason = await critic.evaluate(
        step_id="123", 
        skill_name="test", 
        inputs={}, 
        output="Failed to do it", 
        requirements="success, confirmation"
    )
    
    assert passed is False
    assert "Fallback fail" in reason

@pytest.mark.asyncio
async def test_critic_evaluate_plan_no_requirements(critic):
    passed, reason = await critic.evaluate_plan(
        agent_name="TestAgent",
        tool_calls_data=[{"tool": "action_a", "args": "{}"}],
        history=[],
        requirements=""
    )
    assert passed is True
    assert reason == "No specific plan requirements."
    critic.llm.generate_structured.assert_not_called()

@pytest.mark.asyncio
async def test_critic_evaluate_plan_llm_pass(critic, mock_llm):
    mock_response = MagicMock()
    mock_response.passed = True
    mock_response.reason = "Logical plan"
    mock_llm.generate_structured.return_value = (mock_response, {"total_tokens": 15})

    passed, reason = await critic.evaluate_plan(
        agent_name="TestAgent",
        tool_calls_data=[{"tool": "fetch_data", "args": "{\"source\": \"db\"}"}],
        history=[{"role": "user", "content": "Get the data"}],
        requirements="Must only use safe read endpoints."
    )
    
    assert passed is True
    assert reason == "Logical plan"
    mock_llm.generate_structured.assert_called_once()
    args, kwargs = mock_llm.generate_structured.call_args
    assert "Must only use safe read endpoints." in kwargs["user_prompt"]
    assert "fetch_data" in kwargs["user_prompt"]

@pytest.mark.asyncio
async def test_critic_evaluate_plan_llm_fail(critic, mock_llm):
    mock_response = MagicMock()
    mock_response.passed = False
    mock_response.reason = "Unsafe endpoint used."
    mock_llm.generate_structured.return_value = (mock_response, {"total_tokens": 15})

    passed, reason = await critic.evaluate_plan(
        agent_name="TestAgent",
        tool_calls_data=[{"tool": "delete_db", "args": "{}"}],
        history=[],
        requirements="Must only use safe read endpoints."
    )
    
    assert passed is False
    assert reason == "Unsafe endpoint used."

@pytest.mark.asyncio
async def test_critic_evaluate_plan_llm_exception_fallback(critic, mock_llm):
    mock_llm.generate_structured.side_effect = Exception("API Offline")
    
    passed, reason = await critic.evaluate_plan(
        agent_name="TestAgent",
        tool_calls_data=[{"tool": "fetch_data"}],
        history=[],
        requirements="Check read only"
    )
    
    # For evaluate_plan we fallback to True on exception if not strict
    assert passed is True
    assert "Fallback pass" in reason
