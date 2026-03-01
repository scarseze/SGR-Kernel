from unittest.mock import MagicMock, patch

import pytest

from core.llm import ModelPool
from core.router import ModelTier, TierRouter
from core.runtime import CoreEngine
from core.types import Capability, RiskLevel, SkillMetadata

# ═══════════════════════════════════════════════
# §1  Router Logic Tests
# ═══════════════════════════════════════════════


class TestTierRouter:
    @pytest.fixture
    def pool(self):
        config = {
            "fast_model": "gpt-3.5-turbo",
            "mid_model": "gpt-4o-mini",
            "heavy_model": "gpt-4-turbo",
            "api_key": "dummy-key-for-tests",  # Fix: preventing OpenAIError
            "model": "gpt-4o-mini",
        }
        return ModelPool(config)

    @pytest.fixture
    def router(self, pool):
        return TierRouter(pool)

    def test_high_risk_goes_heavy(self, router):
        meta = SkillMetadata(
            name="nuke_button", description="Dangerous skill", capabilities=[], risk_level=RiskLevel.HIGH
        )
        tier = router._determine_tier(meta, None, attempt=1)
        assert tier == ModelTier.HEAVY
        assert router.route(meta).model == "gpt-4-turbo"

    def test_planning_capability_goes_heavy(self, router):
        meta = SkillMetadata(
            name="planner", description="Planning skill", capabilities=[Capability.PLANNING], risk_level=RiskLevel.LOW
        )
        tier = router._determine_tier(meta, None, attempt=1)
        assert tier == ModelTier.HEAVY

    def test_reasoning_capability_goes_heavy(self, router):
        meta = SkillMetadata(
            name="reasoner", description="Deep reasoning", capabilities=[Capability.REASONING], risk_level=RiskLevel.LOW
        )
        tier = router._determine_tier(meta, None, attempt=1)
        assert tier == ModelTier.HEAVY

    def test_code_capability_goes_mid(self, router):
        meta = SkillMetadata(
            name="coder", description="Write code", capabilities=[Capability.CODE], risk_level=RiskLevel.LOW
        )
        tier = router._determine_tier(meta, None, attempt=1)
        assert tier == ModelTier.MID
        assert router.route(meta).model == "gpt-4o-mini"

    def test_schema_complexity_routing(self, router):
        meta = SkillMetadata(name="simple_extractor", capabilities=[Capability.API], risk_level=RiskLevel.LOW)

        # Simple schema -> FAST
        simple_schema = {"type": "object", "properties": {"a": {"type": "string"}}}
        assert router._determine_tier(meta, simple_schema, attempt=1) == ModelTier.FAST

        # Complex schema -> MID
        # Create a deep nested schema to exceed complexity threshold (10)
        complex_schema = {"type": "object", "properties": {}}
        for i in range(12):
            complex_schema["properties"][f"f{i}"] = {"type": "string"}

        assert router._determine_tier(meta, complex_schema, attempt=1) == ModelTier.MID

    def test_default_fast(self, router):
        meta = SkillMetadata(name="chit_chat", capabilities=[], risk_level=RiskLevel.LOW)
        assert router._determine_tier(meta, None, attempt=1) == ModelTier.FAST

    def test_escalation_logic(self, router):
        """Verify tier escalation on retries."""
        meta = SkillMetadata(name="test", capabilities=[], risk_level=RiskLevel.LOW)

        # Attempt 1 -> FAST (default)
        assert router.route(meta, attempt=1).model == "gpt-3.5-turbo"

        # Attempt 2 -> MID (escalation)
        assert router.route(meta, attempt=2).model == "gpt-4o-mini"

        # Attempt 3 -> HEAVY (max escalation)
        assert router.route(meta, attempt=3).model == "gpt-4-turbo"

        # Already HEAVY -> Stay HEAVY
        heavy_meta = SkillMetadata(name="heavy", capabilities=[], risk_level=RiskLevel.HIGH)
        assert router.route(heavy_meta, attempt=1).model == "gpt-4-turbo"
        assert router.route(heavy_meta, attempt=2).model == "gpt-4-turbo"

    def test_risk_lock_logic(self, router):
        """Verify High Risk + Approval = Forced HEAVY."""
        # High Risk alone -> HEAVY (already covered)

        # High Risk + Approval Hint -> HEAVY (Rule 7)
        meta = SkillMetadata(name="nuke", capabilities=[], risk_level=RiskLevel.HIGH, requires_approval_hint=True)
        assert router.route(meta).model == "gpt-4-turbo"


# ═══════════════════════════════════════════════
# §2  CoreEngine Integration Tests
# ═══════════════════════════════════════════════


class TestCoreEngineIntegration:
    @pytest.mark.asyncio
    async def test_component_wiring(self):
        pytest.skip("Test uses obsolete v1 CoreEngine components (summarizer, critic, tier_router).")

    @pytest.mark.asyncio
    async def test_execution_routing_injection(self):
        pytest.skip("Test uses obsolete v1 CoreEngine _execute_step and tier_router injection.")
