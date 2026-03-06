import asyncio
import json
import logging
import os
import sys

from jinja2 import Template

# Add project root to path so we can import SGR Kernel modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.ui_memory import UIMemory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("safety_case_gen")

# We use a Jinja template to construct Pytest tests
TEST_TEMPLATE = """
import pytest
from unittest.mock import AsyncMock, patch
import json

from core.swarm import SwarmEngine
from core.agent import Agent

# AUTO-GENERATED SAFETY CASE
# Scenario ID: {{ scenario_id }}
# Original Job ID: {{ job_id }}
# Failure Reason: {{ reason }}

@pytest.mark.asyncio
async def test_safety_case_{{ scenario_clean_id }}():
    # 1. Setup Swarm Engine with test config
    engine = SwarmEngine(llm_config={"model": "test-model"})
    
    # 2. Mock the Agent
    agent = Agent(
        name="MockAgent",
        instructions="Handle the task safely.",
        skills=[]
    )
    
    # 3. Load Context Payload
    context_payload = json.loads('''{{ payload | replace("'", "\\'") }}''')
    messages = [
        {"role": "user", "content": f"Execute job: {context_payload}"}
    ]
    
    # 4. Mock the LLM to reproduce the failure condition or test the fix
    # TODO: Developer must adjust this mock to properly simulate the failure
    with patch('core.swarm.SwarmEngine._safe_call_llm', new_callable=AsyncMock) as mock_llm:
        # Mock behavior here...
        pass
        
    # Execute Swarm
    # res, _, _ = await engine.execute(starting_agent=agent, messages=messages, max_turns=3)
    
    # 5. Assertions
    # assert "Error" not in res # Make sure it recovers now
"""

async def generate_offline_tests():
    logger.info("Initializing UI Memory connection...")
    
    # Needs MEMORY_DB_URL set in environment
    if not os.environ.get("MEMORY_DB_URL"):
        # Default to a local sqlite for local dev if not set
        os.environ["MEMORY_DB_URL"] = "sqlite+aiosqlite:///data/memory.sqlite"
        
    memory = UIMemory()
    await memory.initialize()
    
    # Fetch recent failed scenarios
    logger.info("Fetching unresolved safety cases from database...")
    scenarios = await memory.get_unresolved_scenarios(limit=10)
    
    if not scenarios:
        logger.info("No failed scenarios found. System is healthy!")
        return
        
    logger.info(f"Found {len(scenarios)} safety cases to generate.")
    
    output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'tests', 'safety'))
    os.makedirs(output_dir, exist_ok=True)
    
    template = Template(TEST_TEMPLATE)
    
    for scenario in scenarios:
        scenario_id = scenario["scenario_id"]
        job_id = scenario["job_id"]
        reason = scenario["reason"]
        payload = scenario["context_payload"] or "{}"
        
        # Clean ID for python function name
        clean_id = job_id.replace("-", "_").lower()
        
        test_code = template.render(
            scenario_id=scenario_id,
            job_id=job_id,
            reason=reason,
            scenario_clean_id=clean_id,
            payload=payload
        )
        
        filename = f"test_safety_{clean_id}.py"
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(test_code)
            
        logger.info(f"Generated safety test case: {filepath}")

if __name__ == "__main__":
    asyncio.run(generate_offline_tests())
