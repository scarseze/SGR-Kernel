import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.events import EventType
from core.execution import ExecutionStatus, PlanIR, StepNode
from core.runtime import CoreEngine


@pytest.mark.asyncio
async def test_replay_fork():
    """
    Blueprint §10: Replay fork test.
    """
    engine = CoreEngine()

    # 1. Mock Planner
    engine._generate_plan = AsyncMock(
        return_value=PlanIR(steps=[StepNode(id="step1", skill_name="dummy_skill")], edges=[])
    )

    # 2. Mock Skill Adapter
    engine.skill_adapter.execute_skill = AsyncMock(return_value=MagicMock(output="success"))
    engine.lifecycle.critic.evaluate = AsyncMock(return_value=(True, "OK"))

    captured_rid = None
    async def capture_event(event):
        nonlocal captured_rid
        if not captured_rid:
            captured_rid = event.request_id
    engine.events.subscribe(EventType.PLAN_CREATED, capture_event)

    # Run initial
    await engine.run("Initial branch")
    rid_orig = captured_rid
    
    path = engine.checkpoints.get_latest_checkpoint(rid_orig)
    state, _ = engine.checkpoints.load_checkpoint(path)
    events_orig = state.event_log

    # Pick a point to fork
    plan_event = next(e for e in events_orig if e.type == EventType.PLAN_CREATED)

    # 3. Fork
    await engine.fork(rid_orig, plan_event.event_id)
    # Finding the fork request id
    rid_fork = [rid for rid in engine.active_executions.keys() if rid != rid_orig][0]

    assert rid_orig != rid_fork
    assert "-fork-" in rid_fork

    state_fork = engine.active_executions[rid_fork]
    assert state_fork.status == ExecutionStatus.RUNNING or state_fork.status == ExecutionStatus.COMPLETED

    print(f"✅ Replay Fork Verified with Mocks! Forked {rid_orig} -> {rid_fork}")


if __name__ == "__main__":
    asyncio.run(test_replay_fork())
