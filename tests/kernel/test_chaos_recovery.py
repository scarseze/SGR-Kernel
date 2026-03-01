import os
import sys
import unittest
import asyncio

# Ensure project roots are on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "SA", "sgr_kernel"))

from core.chaos import ChaosException, with_chaos
from core.agent import Agent
from core.swarm import SwarmEngine

class TestChaosEngineering(unittest.TestCase):
    def setUp(self):
        os.environ["ENABLE_CHAOS"] = "true"
        os.environ.setdefault("LLM_MODEL", "mock-model")
        
    def tearDown(self):
        os.environ.pop("ENABLE_CHAOS", None)
        os.environ.pop("CHAOS_FAILURE_RATE", None)
        os.environ.pop("CHAOS_MAX_DELAY", None)

    def test_chaos_decorator_failure(self):
        os.environ["CHAOS_FAILURE_RATE"] = "1.0"
        os.environ["CHAOS_MAX_DELAY"] = "0.0"

        @with_chaos
        def dummy_function():
            return "success"
            
        with self.assertRaises(ChaosException):
            dummy_function()

    def test_chaos_decorator_success(self):
        os.environ["CHAOS_FAILURE_RATE"] = "0.0"
        os.environ["CHAOS_MAX_DELAY"] = "0.0"

        @with_chaos
        def dummy_function():
            return "success"
            
        self.assertEqual(dummy_function(), "success")

    def test_swarm_handles_llm_failure(self):
        """
        Verify that if the LLM fails completely (after tenacity retries if we had them, 
        or if it raises an unhandled exception), the SwarmEngine catches it and doesn't crash the server.
        """
        os.environ["CHAOS_FAILURE_RATE"] = "1.0"
        os.environ["CHAOS_MAX_DELAY"] = "0.0"
        
        engine = SwarmEngine({})
        agent = Agent(name="TestAgent", instructions="Test")
        
        async def run():
            msg, _, _ = await engine.execute(
                starting_agent=agent,
                messages=[{"role": "user", "content": "Hello"}]
            )
            return msg
            
        
        # SwarmEngine gracefully catches the exception and returns an error string
        # This is the desired behavior (no server crash). 
        result_msg = asyncio.run(run())
        self.assertIn("Error connecting to LLM", result_msg)
        self.assertIn("ChaosMonkey", result_msg)

if __name__ == '__main__':
    unittest.main()
