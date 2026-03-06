from unittest.mock import AsyncMock, MagicMock

import pytest

from core.container import Container
from core.events import EventType, KernelEvent
from core.execution import ExecutionState, FailureRecord, RetryPolicy, SemanticFailureType, StepNode, StepStatus
from core.orchestrator import ExecutionOrchestrator


@pytest.fixture
def mock_events():
    bus = AsyncMock()
    Container.register("event_bus", bus)
    return bus

@pytest.fixture
def mock_scheduler():
    sched = AsyncMock()
    # Mock result with complete failure from Critic so retry attempts == max_attempts
    res = MagicMock()
    res.success = False
    
    # We will dynamically overwrite Events in the test
    sched.dispatch.return_value = [res]
    return sched

@pytest.fixture
def orchestrator(mock_events, mock_scheduler):
    # Mock lifecycle before Orchestrator init
    mock_lifecycle = AsyncMock()
    Container.register("lifecycle", mock_lifecycle)
    Container.register("redis", AsyncMock())
    
    orch = ExecutionOrchestrator()
    orch.scheduler = mock_scheduler
    return orch

@pytest.mark.asyncio
async def test_human_approval_fallback(orchestrator, mock_events, mock_scheduler):
    # Register approval callback
    approval_called = False
    async def fake_approval(msg):
        nonlocal approval_called
        approval_called = True
        return True # Approve fallback
    
    Container.register("approval_callback", fake_approval)
    
    # Setup State
    state = ExecutionState(request_id="test_req", input_payload="test")
    step = StepNode(id="step_1", skill_name="test_skill", critic_required=True, retry_policy=RetryPolicy(max_attempts=1))
    
    # Fake Graph Engine returns this step first time
    mock_graph_engine_instance = MagicMock()
    mock_graph_engine_instance.is_complete.side_effect = [False, True]
    mock_graph_engine_instance.get_runnable_steps.side_effect = [[step], []]
    mock_graph_engine_instance.steps_lut = {"step_1": step}
    
    with pytest.MonkeyPatch.context() as m:
        m.setattr("core.orchestrator.ExecutionGraphEngine", MagicMock(return_value=mock_graph_engine_instance))
        
        # Init step state at max attempts
        state.initialize_step("step_1")
        state.step_states["step_1"].attempts = 1
        
        # Setup the simulated failure event from the scheduler
        fail_rec = FailureRecord(
            step_id="step_1",
            failure_type=SemanticFailureType.CRITIC_FAIL,
            phase="VALIDATE",
            error_class="ValueError",
            retryable=True,
            repairable=True,
            error_message="Bad Output"
        )
        
        fail_event = KernelEvent(
            type=EventType.STEP_FAILED,
            request_id="test_req",
            step_id="step_1",
            payload={"failure": fail_rec}
        )
        mock_scheduler.dispatch.return_value[0].events = [fail_event]
        
        # Execute
        await orchestrator.execute(state)
        
        # Verify approval was invoked
        assert approval_called is True
        
        # Verify step was force committed by the human
        assert state.step_states["step_1"].status == StepStatus.COMMITTED
        
        # Verify pause event was sent
        pause_events = [c.args[0] for c in mock_events.publish.mock_calls if c.args[0].type == EventType.EXECUTION_PAUSED]
        assert len(pause_events) == 1
        assert pause_events[0].payload["reason"] == "CRITIC_FAIL_ESCALATION"

@pytest.mark.asyncio
async def test_human_rejection_fallback(orchestrator, mock_events, mock_scheduler):
    # Register rejecting callback
    async def fake_approval(msg):
        return False # Reject fallback
    
    Container.register("approval_callback", fake_approval)
    
    state = ExecutionState(request_id="test_req_2", input_payload="test")
    step = StepNode(id="step_1", skill_name="test_skill", critic_required=True, retry_policy=RetryPolicy(max_attempts=1))
    
    mock_graph_engine_instance = MagicMock()
    mock_graph_engine_instance.is_complete.return_value = False
    mock_graph_engine_instance.get_runnable_steps.side_effect = [[step], []]
    mock_graph_engine_instance.steps_lut = {"step_1": step}
    
    with pytest.MonkeyPatch.context() as m:
        m.setattr("core.orchestrator.ExecutionGraphEngine", MagicMock(return_value=mock_graph_engine_instance))
        
        state.initialize_step("step_1")
        state.step_states["step_1"].attempts = 1
        
        fail_rec = FailureRecord(
            step_id="step_1",
            failure_type=SemanticFailureType.CRITIC_FAIL,
            phase="VALIDATE",
            error_class="ValueError",
            retryable=True,
            repairable=True,
            error_message="Bad Output"
        )
        
        fail_event = KernelEvent(
            type=EventType.STEP_FAILED,
            request_id="test_req_2",
            step_id="step_1",
            payload={"failure": fail_rec}
        )
        mock_scheduler.dispatch.return_value[0].events = [fail_event]
        
        await orchestrator.execute(state)
        
        # Verify execution was aborted
        from core.execution import ExecutionStatus
        assert state.status == ExecutionStatus.ABORTED
