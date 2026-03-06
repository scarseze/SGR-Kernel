from unittest.mock import AsyncMock, MagicMock

import pytest

from core.critic import CriticEngine
from core.metrics import AnswerRelevancyMetric, CostLimitMetric

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
    assert reason == "No specific requirements or metrics."
    critic.llm.generate.assert_not_called()

@pytest.mark.asyncio
async def test_critic_evaluate_llm_pass(critic, mock_llm):
    # Setup mock to return a passing float string for RequirementsMetric
    mock_llm.generate.return_value = ("1.0", {"total_tokens": 10})

    passed, reason = await critic.evaluate(
        step_id="123", 
        skill_name="test_skill", 
        inputs={"data": "test"}, 
        output="The file was created successfully.", 
        requirements="Must confirm file creation."
    )
    
    assert passed is True
    assert "All metrics passed" in reason
    mock_llm.generate.assert_called_once()
    args, kwargs = mock_llm.generate.call_args
    assert "Must confirm file creation." in kwargs["user_prompt"]
    assert "The file was created successfully." in kwargs["user_prompt"]

@pytest.mark.asyncio
async def test_critic_evaluate_llm_fail(critic, mock_llm):
    # Setup mock to return a failing float string calculation
    mock_llm.generate.return_value = ("0.0", {"total_tokens": 10})

    passed, reason = await critic.evaluate(
        step_id="123", 
        skill_name="test_skill", 
        inputs={}, 
        output="Done.", 
        requirements="Must confirm file creation."
    )
    
    assert passed is False
    assert "Failed metric" in reason

@pytest.mark.asyncio
async def test_critic_evaluate_fallback_pass(critic, mock_llm):
    # Make the LLM call throw an exception to trigger the fallback logic in RequirementsMetric
    mock_llm.generate.side_effect = Exception("API Error")

    passed, reason = await critic.evaluate(
        step_id="123", 
        skill_name="test", 
        inputs={}, 
        output="Success confirmation status", 
        requirements="success, confirmation"
    )
    
    assert passed is True
    assert "All metrics passed" in reason

@pytest.mark.asyncio
async def test_critic_evaluate_fallback_fail(critic, mock_llm):
    # Make the LLM call throw an exception to trigger the fallback
    mock_llm.generate.side_effect = Exception("API Error")

    passed, reason = await critic.evaluate(
        step_id="123", 
        skill_name="test", 
        inputs={}, 
        output="Failed to do it", 
        requirements="success, confirmation"
    )
    
    assert passed is False
    assert "Failed metric" in reason

@pytest.mark.asyncio
async def test_critic_evaluate_plan_no_requirements(critic):
    passed, reason = await critic.evaluate_plan(
        agent_name="TestAgent",
        tool_calls_data=[{"tool": "action_a", "args": "{}"}],
        history=[],
        requirements=""
    )
    assert passed is True
    assert reason == "No specific plan requirements or metrics."
    critic.llm.generate.assert_not_called()

@pytest.mark.asyncio
async def test_critic_evaluate_plan_llm_pass(critic, mock_llm):
    mock_llm.generate.return_value = ("1.0", {"total_tokens": 15})

    passed, reason = await critic.evaluate_plan(
        agent_name="TestAgent",
        tool_calls_data=[{"tool": "fetch_data", "args": "{\"source\": \"db\"}"}],
        history=[{"role": "user", "content": "Get the data"}],
        requirements="Must only use safe read endpoints."
    )
    
    assert passed is True
    assert "Plan passed all metrics" in reason
    mock_llm.generate.assert_called_once()

@pytest.mark.asyncio
async def test_critic_evaluate_plan_llm_fail(critic, mock_llm):
    mock_llm.generate.return_value = ("0.0", {"total_tokens": 15})

    passed, reason = await critic.evaluate_plan(
        agent_name="TestAgent",
        tool_calls_data=[{"tool": "delete_db", "args": "{}"}],
        history=[],
        requirements="Must only use safe read endpoints."
    )
    
    assert passed is False
    assert "Plan failed metric" in reason

@pytest.mark.asyncio
async def test_critic_evaluate_plan_llm_exception_fallback(critic, mock_llm):
    mock_llm.generate.side_effect = Exception("API Offline")
    
    passed, reason = await critic.evaluate_plan(
        agent_name="TestAgent",
        tool_calls_data=[{"tool": "fetch_data"}],
        history=[],
        requirements="Check read only",
        metrics=[CostLimitMetric(10.0)] # Also test with an explicit metric
    )
    
    # Requirements metric falls back to keyword matching, which might fail or pass depending on output.
    # CostLimitMetric always passes here.
    assert passed is False # Keyword matcher will fail because "Check read only" is not in the output.

@pytest.mark.asyncio
async def test_critic_with_custom_metrics(critic, mock_llm):
    mock_llm.generate.return_value = ("1.0", {})
    metrics = [
        AnswerRelevancyMetric(mock_llm, threshold=0.8),
        CostLimitMetric(max_cost_usd=0.05)
    ]
    
    passed, reason = await critic.evaluate(
        step_id="123",
        skill_name="test",
        inputs={"query": "What is 2+2?"},
        output="4",
        metrics=metrics
    )
    
    assert passed is True
    assert "All metrics passed" in reason
    mock_llm.generate.assert_called_once()
