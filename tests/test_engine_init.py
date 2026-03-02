import os
import sys
import unittest
from unittest.mock import patch

# Ensure project root in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.runtime import CoreEngine


class TestEngineInit(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Mock external dependencies
        self.mock_redis_patch = patch("redis.asyncio.Redis")
        self.mock_redis = self.mock_redis_patch.start()

    async def asyncTearDown(self):
        self.mock_redis_patch.stop()

    def test_lifecycle_components_initialized(self):
        """Verify Lifecycle components are initialized in v2."""
        engine = CoreEngine(llm_config={"api_key": "dummy"})

        # Check attributes existence
        self.assertTrue(hasattr(engine, "lifecycle"))
        self.assertTrue(hasattr(engine.lifecycle, "critic"))
        self.assertTrue(hasattr(engine.lifecycle, "repair"))
        self.assertTrue(hasattr(engine.lifecycle, "reliability"))

        print("Engine Lifecycle initialization verify: SUCCESS")


if __name__ == "__main__":
    unittest.main()
