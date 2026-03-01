import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.execution import DependencyEdge, PlanIR, StepNode
from core.runtime import CoreEngine
from core.state_manager import StateManager


@pytest.mark.asyncio
async def test_event_determinism():
    """
    Blueprint §10: Event determinism test.
    """
    engine = CoreEngine()

    # 1. Mock Planner to return a simple plan
    engine._generate_plan = AsyncMock(
        return_value=PlanIR(
            steps=[StepNode(id="step1", skill_name="dummy_skill"), StepNode(id="step2", skill_name="dummy_skill")],
            edges=[DependencyEdge(source_id="step1", target_id="step2")],
        )
    )

    # 2. Mock Skill Adapter
    engine.skill_adapter.execute_skill = AsyncMock(return_value=MagicMock(output="success"))

    # 3. Mock Critic to always pass
    engine.lifecycle.critic.evaluate = AsyncMock(return_value=(True, "OK"))

    from core.events import EventType

    captured_rid = None
    async def capture_event(event):
        nonlocal captured_rid
        if not captured_rid:
            captured_rid = event.request_id
    engine.events.subscribe(EventType.PLAN_CREATED, capture_event)

    # Run
    await engine.run("Mocked input")

    rid = captured_rid
    path = engine.checkpoints.get_latest_checkpoint(rid)
    state1, _ = engine.checkpoints.load_checkpoint(path)

    # Reconstruct state2
    state2 = StateManager.reconstruct(state1.event_log, rid)

    # Assertions
    assert state1.status == state2.status
    assert state1.skill_outputs == state2.skill_outputs
    assert len(state1.event_log) == len(state2.event_log)

    for sid, s_state1 in state1.step_states.items():
        s_state2 = state2.step_states[sid]
        assert s_state1.status == s_state2.status
        assert s_state1.output == s_state2.output

    print("✅ Event Determinism Verified with Mocks!")


if __name__ == "__main__":
    asyncio.run(test_event_determinism())
