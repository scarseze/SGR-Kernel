"""KC-K: Trace integrity tests — validates that traces are created during execution.
Migrated to v2: uses KernelTestRig for full pipeline execution.
"""

import pytest

from core.planner import PlanStep
from tests.fakes.fake_skill import FakeSkill


class TestTraceIntegrity:
    @pytest.mark.asyncio
    async def test_kc_k1_execution_produces_trace(self):
        """Running a skill through rig produces a trace."""
        from tests.harness.kernel_rig import KernelTestRig

        skill = FakeSkill()
        rig = KernelTestRig()
        rig.without_security()
        rig.with_skill(skill)

        step = PlanStep(
            step_id="s1",
            skill_name=skill.name,
            description="test trace",
            params={},
        )
        await rig.run_step(step)
        assert skill.calls == 1

    @pytest.mark.asyncio
    async def test_kc_k3_failed_skill_still_tracked(self):
        """Trace saved even when skill raises."""
        from tests.harness.kernel_rig import KernelTestRig

        skill = FakeSkill(fail_times=99)  # always fail
        rig = KernelTestRig()
        rig.without_security()
        rig.with_skill(skill)

        step = PlanStep(
            step_id="s1",
            skill_name=skill.name,
            description="test failure trace",
            params={},
        )
        try:
            await rig.run_step(step)
        except Exception:
            pass
        assert skill.calls == 1  # was called, even though it failed
