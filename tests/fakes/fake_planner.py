"""FakePlanner — returns pre-configured plans without LLM calls."""

from core.planner import ExecutionPlan, PlanStep
from core.types import RetryPolicy


class FakePlanner:
    def __init__(self, plan=None, direct_response=None, engine=None):
        self.plan = plan
        self.direct_response = direct_response
        self.engine = engine
        self.create_plan_calls = 0
        self.repair_plan_calls = 0

    async def create_plan(self, text, skills_desc, history):
        self.create_plan_calls += 1

        if self.direct_response:
            return ExecutionPlan(steps=[], reasoning="direct", direct_response=self.direct_response), {
                "model": "fake",
                "total_cost": 0.0,
            }

        if self.plan:
            return self.plan, {"model": "fake", "total_cost": 0.0}

        # Try to find skill metadata from common test patterns
        retry_p = RetryPolicy.STANDARD
        timeout = 300.0
        
        if self.engine and "fake" in self.engine.skills:
             meta = self.engine.skills["fake"].metadata
             retry_p = meta.retry_policy
             timeout = meta.timeout_sec

        step = PlanStep(
            step_id="s1", 
            skill_name="fake", 
            description="default step", 
            params={"x": 1}, 
            depends_on=[],
            retry_policy=retry_p,
            timeout_sec=timeout
        )
        # HACK: If we are in a test and it needs a specific policy, we should allow it.
        # But wait, the test test_rig_retry_none_no_retry creates a rig with a skill.
        # It doesn't tell the planner what to do.
        # So the planner MUST look at the skill metadata.
        return ExecutionPlan(steps=[step], reasoning="default"), {"model": "fake", "total_cost": 0.0}

    async def repair_plan(self, *a, **k):
        self.repair_plan_calls += 1
        return None
