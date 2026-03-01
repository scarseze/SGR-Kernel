import asyncio
import logging
import os
import sys
from unittest.mock import AsyncMock

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.events import EventType
from core.planner import ExecutionPlan, PlanStep
from core.runtime import CoreEngine
from core.skill_interface import Skill, SkillContext, SkillResult
from core.state_manager import StateManager

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("replay_test")


class SimpleSkill(Skill):
    def __init__(self, name, output="Done"):
        self._name = name
        self._output = output
        self._capabilities = set()

    @property
    def name(self):
        return self._name

    @property
    def capabilities(self):
        return self._capabilities

    async def execute(self, ctx: SkillContext) -> SkillResult:
        return SkillResult(output=self._output)


async def test_recon_and_replay():
    engine = CoreEngine(llm_config={"api_key": "dummy"})
    engine.register_skill(SimpleSkill("step_a", "Result A"))
    engine.register_skill(SimpleSkill("step_b", "Result B"))

    mock_plan = ExecutionPlan(
        steps=[
            PlanStep(step_id="a", skill_name="step_a", description="Task A", params={}),
            PlanStep(step_id="b", skill_name="step_b", description="Task B", params={}, depends_on=["a"]),
        ],
        reasoning="Sequential plan for replay test.",
    )
    engine.planner.create_plan = AsyncMock(return_value=(mock_plan, {}))

    captured_rid = None
    async def capture_event(event):
        nonlocal captured_rid
        if not captured_rid:
            captured_rid = event.request_id
    engine.events.subscribe(EventType.PLAN_CREATED, capture_event)

    logger.info("Running initial execution...")
    await engine.run("Test run")

    request_id = captured_rid
    path = engine.checkpoints.get_latest_checkpoint(request_id)
    original_state, _ = engine.checkpoints.load_checkpoint(path)
    original_events = original_state.event_log

    logger.info(f"Execution finished with {len(original_events)} events.")

    # --- 1. Test Reconstruction ---
    logger.info("Testing Reconstruction...")
    reconstructed_state = StateManager.reconstruct(original_events)

    assert reconstructed_state.request_id == original_state.request_id
    assert reconstructed_state.status == original_state.status
    assert reconstructed_state.skill_outputs["a"] == "Result A"
    assert reconstructed_state.skill_outputs["b"] == "Result B"
    logger.info("✅ Reconstruction match successful!")

    # --- 2. Test Replay (Rollback) ---
    logger.info("Testing Replay (Rollback to step_a completed)...")
    # Find event where step 'a' finished
    target_event_id = None
    for e in original_events:
        if e.type == EventType.STEP_COMPLETED and e.step_id == "a":
            target_event_id = e.event_id
            break

    assert target_event_id is not None

    # Reset engine and replay
    new_engine = CoreEngine(llm_config={"api_key": "dummy"})
    # Need to re-register skills or use the same engine instance with cleared active_executions
    new_engine.register_skill(SimpleSkill("step_a", "Result A"))
    new_engine.register_skill(
        SimpleSkill("step_b", "Result B - Replayed")
    )  # Change output to verify it actually re-ran
    new_engine.planner.create_plan = AsyncMock(return_value=(mock_plan, {}))

    # We manually trigger checkpoint saving for the new engine to find the old state
    # Actually, replay() looks at checkpoints. We can just use the same engine instance.

    logger.info(f"Replaying up to event {target_event_id}...")
    # Update Skill B to show it re-executed
    engine.skills["step_b"]._output = "Result B - Replayed"

    replay_result = await engine.replay(request_id, up_to_event_id=target_event_id)
    logger.info(f"Replay Result: {replay_result}")

    assert "Result B - Replayed" in replay_result
    assert "Result A" in replay_result  # Should still be in outputs from reconstruction

    logger.info("✅ Replay test passed!")


if __name__ == "__main__":
    asyncio.run(test_recon_and_replay())
