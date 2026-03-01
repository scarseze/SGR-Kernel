import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.events import EventType
from core.execution import PlanIR, StepNode
from core.runtime import CoreEngine


@pytest.mark.asyncio
async def test_race_safety_parallel():
    """
    Blueprint §10: Parallelism test (race safety).
    Checks that no double execution occurs and state remains consistent.
    """
    engine = CoreEngine()

    # 1. Mock Planner to return 3 parallel steps
    engine._generate_plan = AsyncMock(
        return_value=PlanIR(
            steps=[
                StepNode(id="step1", skill_name="dummy_skill"),
                StepNode(id="step2", skill_name="dummy_skill"),
                StepNode(id="step3", skill_name="dummy_skill"),
            ],
            edges=[],  # No dependencies = parallel
        )
    )

    # 2. Mock Skill Adapter with a slight delay to ensure parallelism
    async def delayed_skill(*args, **kwargs):
        await asyncio.sleep(0.1)
        return MagicMock(output="success")

    engine.skill_adapter.execute_skill = AsyncMock(side_effect=delayed_skill)
    engine.lifecycle.critic.evaluate = AsyncMock(return_value=(True, "OK"))

    captured_rid = None
    async def capture_event(event):
        nonlocal captured_rid
        if not captured_rid:
            captured_rid = event.request_id
    engine.events.subscribe(EventType.PLAN_CREATED, capture_event)

    # Run
    await engine.run("Run parallel wave")

    rid = captured_rid
    path = engine.checkpoints.get_latest_checkpoint(rid)
    state, _ = engine.checkpoints.load_checkpoint(path)

    # Debug print event log
    print(f"\nDEBUG: Event Log for {rid}:")
    for e in state.event_log:
        print(f"  Type: {e.type} (val={e.type.value}), Step: {e.step_id}")

    # Verify that each step has ONLY ONE STARTED event and ONE COMPLETED event
    step_events = {}  # step_id -> [event_types]
    for event in state.event_log:
        if event.step_id:
            step_events.setdefault(event.step_id, []).append(event.type)

    for sid, types in step_events.items():
        count_started = sum(1 for t in types if t == EventType.STEP_STARTED)
        count_completed = sum(1 for t in types if t == EventType.STEP_COMPLETED)
        assert count_started == 1, f"Step {sid} started {count_started} times (expected 1). Events: {types}"
        assert count_completed == 1, f"Step {sid} completed {count_completed} times (expected 1). Events: {types}"

    print("✅ Race Safety (Parallel) Verified with Mocks!")


if __name__ == "__main__":
    from core.events import EventType  # Local import

    asyncio.run(test_race_safety_parallel())
