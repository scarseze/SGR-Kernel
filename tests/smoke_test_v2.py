import asyncio
import logging
import os
import sys
from unittest.mock import AsyncMock

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.events import EventType
from core.execution import ExecutionStatus
from core.planner import ExecutionPlan, PlanStep
from core.runtime import CoreEngine
from core.skill_interface import Skill, SkillContext, SkillResult

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("smoke_test")


class MockSkill(Skill):
    def __init__(self, name, output="Success"):
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
        logger.info(f"Executing MockSkill: {self.name}")
        return SkillResult(output=self._output)


async def test_event_driven_flow():
    """
    Verifies:
    1. CoreEngine initializes
    2. Events are published
    3. State is updated via StateManager
    4. Orchestrator completes DAG
    """
    engine = CoreEngine(llm_config={"api_key": "dummy"})

    # Mock Planner to avoid real LLM calls
    mock_plan = ExecutionPlan(
        steps=[
            PlanStep(step_id="step_1", skill_name="research", description="Research AI", params={}),
            PlanStep(
                step_id="step_2", skill_name="writer", description="Write summary", params={}, depends_on=["step_1"]
            ),
        ],
        reasoning="Simple research then write plan.",
    )
    engine.planner.create_plan = AsyncMock(return_value=(mock_plan, {}))

    # Register skills
    engine.register_skill(MockSkill("research"))
    engine.register_skill(MockSkill("writer"))

    # Capture events for verification
    event_log = []

    async def capture_event(event):
        event_log.append(event)
        logger.info(f"Captured: {event.type}")
        if event.type == EventType.STEP_FAILED:
            failure = event.payload.get("failure")
            if failure:
                # failure is a FailureRecord or dict
                msg = getattr(failure, "error_message", str(failure))
                logger.error(f"❌ Step {event.step_id} failed: {msg}")

    engine.events.subscribe_all(capture_event)

    # Run engine
    logger.info("Starting Engine...")
    user_input = "Write a report about AI"
    await engine.run(user_input)

    logger.info(f"Result: {result}")

    # Verify events
    types = [e.type for e in event_log]
    assert EventType.PLAN_CREATED in types
    assert EventType.EXECUTION_STARTED in types
    assert EventType.STEP_STARTED in types
    assert EventType.STEP_COMPLETED in types
    assert EventType.EXECUTION_COMPLETED in types

    # Verify state updates
    for _, state in engine.active_executions.items():
        assert state.status == ExecutionStatus.COMPLETED
        assert len(state.event_log) > 0
        logger.info(f"State event log length: {len(state.event_log)}")

    logger.info("✅ Smoke test passed!")


if __name__ == "__main__":
    asyncio.run(test_event_driven_flow())
