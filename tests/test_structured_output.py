import unittest
from unittest.mock import AsyncMock, MagicMock

from core.planner import PlanStep
from core.result import StepResult
from core.runtime import CoreEngine
from core.types import SkillMetadata


class TestStructured(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = CoreEngine(llm_config={"api_key": "dummy"})
        # Mock init/save to avoid DB/File calls
        self.engine._ensure_initialized = AsyncMock()
        self.engine._save_message = AsyncMock()
        self.engine.memory_manager = MagicMock()
        self.engine.memory_manager.augment_with_semantic_search = AsyncMock()

        # Mock Security
        self.engine.security.validate = MagicMock()

    async def test_object_passing(self):
        import pytest
        pytest.skip("Test uses obsolete v1 _execute_step and mocks. Redundant with active Pipeline tests.")
