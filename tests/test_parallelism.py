import asyncio

import pytest

pytestmark = pytest.mark.asyncio
import os
import sys
import time
from unittest.mock import AsyncMock

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import logging

from core.execution import ExecutionStatus
from core.planner import ExecutionPlan, PlanStep
from core.runtime import CoreEngine
from core.skill_interface import Skill, SkillContext, SkillResult

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("parallel_test")


class SlowSkill(Skill):
    def __init__(self, name, delay=2):
        self._name = name
        self._delay = delay
        self._capabilities = set()

    @property
    def name(self):
        return self._name

    @property
    def capabilities(self):
        return self._capabilities

    @property
    def metadata(self):
        from core.types import CostClass, RiskLevel, SkillMetadata
        return SkillMetadata(
            capabilities=[],
            risk_level=RiskLevel.LOW,
            cost_class=CostClass.CHEAP,
            side_effects=False,
            idempotent=True,
            requires_network=False,
            requires_filesystem=False
        )

    def input_schema(self, **kwargs):
        return kwargs

    async def execute(self, ctx: SkillContext) -> SkillResult:
        logger.info(f"⏳ Step {self.name} starting (will take {self._delay}s)...")
        await asyncio.sleep(self._delay)
        logger.info(f"✅ Step {self.name} finished.")
        return SkillResult(output=f"Result from {self.name}")


async def test_parallel_execution():
    """
    Verifies that independent steps run concurrently.
    DAG:
    step_1 (2s) \
                 > step_3 (1s)
    step_2 (2s) /
    Total time should be ~3s if parallel, ~5s if sequential.
    """
    engine = CoreEngine(llm_config={"api_key": "dummy"})

    # Mock Planner: step_1 and step_2 are independent, step_3 depends on both
    mock_plan = ExecutionPlan(
        steps=[
            PlanStep(step_id="step_1", skill_name="skill_1", description="Task 1", params={}),
            PlanStep(step_id="step_2", skill_name="skill_2", description="Task 2", params={}),
            PlanStep(
                step_id="step_3",
                skill_name="skill_3",
                description="Combine",
                params={},
                depends_on=["step_1", "step_2"],
            ),
        ],
        reasoning="Parallel branching test.",
    )
    engine.planner.create_plan = AsyncMock(return_value=(mock_plan, {}))

    # Register skills
    engine.register_skill(SlowSkill("skill_1", delay=2))
    engine.register_skill(SlowSkill("skill_2", delay=2))
    engine.register_skill(SlowSkill("skill_3", delay=1))

    start_time = time.time()

    logger.info("Starting Parallel Execution Test...")
    await engine.run("Run parallel test")

    duration = time.time() - start_time
    logger.info(f"Total Duration: {duration:.2f}s")

    # Verify parallelism
    # If sequential: 2 + 2 + 1 = 5s
    # If parallel: max(2, 2) + 1 = 3s
    assert duration < 4.5, f"Execution too slow ({duration:.2f}s), parallelism might be broken!"
    assert duration >= 3.0, "Execution too fast?"

    # Verify state
    for _, state in engine.active_executions.items():
        assert state.status == ExecutionStatus.COMPLETED
        # Check overlaps in timestamps to be sure
        s1 = state.step_states["step_1"]
        s2 = state.step_states["step_2"]

        # Determine if they overlapped
        # [s1.start, s1.end] vs [s2.start, s2.end]
        overlap = min(s1.finished_at, s2.finished_at) - max(s1.started_at, s2.started_at)
        logger.info(f"Measured overlap: {overlap:.2f}s")
        assert overlap > 1.5, "Steps did not run in parallel!"

    logger.info("✅ Parallelism test passed!")


if __name__ == "__main__":
    asyncio.run(test_parallel_execution())
