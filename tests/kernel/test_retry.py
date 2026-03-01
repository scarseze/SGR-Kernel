"""KC-E: Retry system tests — count mapping, fatal errors, is_retry, backoff.
Migrated to v2: uses KernelTestRig for execution, pure unit test for SkillExecutionContext.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.middleware import HumanDenied, PolicyDenied
from core.planner import PlanStep
from core.types import RetryPolicy, SkillExecutionContext, StepStatus
from tests.kernel.conftest import make_skill


class TestRetrySystem:
    def _make_plan_step(self, skill_name="fake"):
        return PlanStep(
            step_id="s1",
            skill_name=skill_name,
            description="test",
            params={},
        )

    @pytest.mark.asyncio
    async def test_kc_e1_retry_count_none(self):
        """NONE → 1 attempt."""
        from tests.harness.kernel_rig import KernelTestRig
        from tests.fakes.fake_skill import FakeSkill

        skill = FakeSkill(fail_times=99)  # always fail
        rig = KernelTestRig()
        rig.without_security()
        rig.with_skill(skill)

        try:
            await rig.run_step(self._make_plan_step(skill.name))
        except Exception:
            pass
        # FakeSkill has no retry by default (NONE) → 1 call
        assert skill.calls == 1

    def test_kc_e3_is_retry_correctness(self):
        """attempt 1 → False, attempt > 1 → True."""
        ctx = SkillExecutionContext(
            request_id="r1",
            step_id="s1",
            skill_name="test",
            params={},
            state=MagicMock(),
            skill=MagicMock(),
            metadata=make_skill().metadata,
            trace=MagicMock(),
            attempt=1,
        )
        assert ctx.is_retry is False
        ctx.attempt = 2
        assert ctx.is_retry is True
        ctx.attempt = 5
        assert ctx.is_retry is True
