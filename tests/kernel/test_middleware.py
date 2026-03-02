"""KC-D: Step execution pipeline tests — middleware ordering, metadata validation.
Migrated to v2: uses KernelTestRig for middleware ordering.
"""

from unittest.mock import MagicMock

import pytest

from core.middleware import SkillMiddleware
from core.planner import PlanStep
from core.types import SkillMetadata
from tests.kernel.conftest import _EngineStub


class TestStepPipeline:
    @pytest.mark.asyncio
    async def test_kc_d1_middleware_order(self):
        """KC-D1: before=forward, after=reversed."""
        from tests.fakes.fake_skill import FakeSkill
        from tests.harness.kernel_rig import KernelTestRig

        call_log = []

        class OrderedMW(SkillMiddleware):
            def __init__(self, name):
                self._name = name

            async def before_execute(self, ctx):
                call_log.append(f"before:{self._name}")

            async def after_execute(self, ctx, result):
                call_log.append(f"after:{self._name}")
                return result

        rig = KernelTestRig()
        rig.without_security()
        skill = FakeSkill()
        rig.with_skill(skill)
        rig.with_middlewares([
            OrderedMW("Trace"),
            OrderedMW("Policy"),
            OrderedMW("Approval"),
            OrderedMW("Timeout"),
        ])

        step = PlanStep(
            step_id="s1",
            skill_name=skill.name,
            description="test",
            params={},
        )
        await rig.run_step(step)

        before = [c for c in call_log if c.startswith("before:")]
        after = [c for c in call_log if c.startswith("after:")]

        assert before == [
            "before:Trace",
            "before:Policy",
            "before:Approval",
            "before:Timeout",
        ]
        # v2 governance hooks fire after_execute in registration order (forward)
        assert after == [
            "after:Trace",
            "after:Policy",
            "after:Approval",
            "after:Timeout",
        ]

    def test_kc_d2_metadata_normalization(self):
        """KC-D2: Dict metadata auto-converted to SkillMetadata."""
        engine = _EngineStub()
        skill = MagicMock()
        skill.name = "raw_skill"
        skill.metadata = {
            "name": "raw_skill",
            "capabilities": ["reasoning"],
            "description": "test",
        }
        engine.register_skill(skill)
        assert isinstance(engine.skills["raw_skill"].metadata, SkillMetadata)
