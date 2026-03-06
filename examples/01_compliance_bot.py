#!/usr/bin/env python3
"""
SGR Kernel V3 Enterprise Example: Compliance Bot (152-FZ)

This demonstrates the Phase 9 Regulatory Compliance Engine and Phase 10 OutputSpec DSL.
It ensures that processing of personal data (like passport numbers) is strictly regulated 
and verified before hitting LLM providers or databases.
"""

import asyncio
import os
import sys

# Add parent dir to path to find core modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.swarm import SwarmEngine
from core.agent import Agent
from core.execution import ExecutionPlan, PlanStep
from core.verification.output_spec import OutputSpec

async def main():
    print("🛡️ Starting Compliance Bot Demo (152-FZ)")
    print("---------------------------------------")

    # 1. Initialize Swarm Engine
    engine = SwarmEngine()

    # 2. Define a strict Output Specification (Phase 10)
    # This guarantees the LLM will not hallucinate PII or bad JSON formats.
    safe_data_spec = OutputSpec("SafeUserData") \
        .requires_json() \
        .forbids_pii() \
        .max_length(500)

    # 3. Create a Data Processing Agent
    data_agent = Agent(
        name="DataProcessor",
        model="gpt-4-turbo", # We will try to use this, but compliance might override
        instructions="You process user forms and return JSON summaries of their requests.",
        output_spec=safe_data_spec
    )
    engine.register_agent(data_agent)

    # 4. Create an Execution Plan
    plan = ExecutionPlan(
        request_id="demo_compliance_001",
        input_payload={"user_query": "Hello, my passport is 12 34 567890. Please update my address."},
    )
    plan.add_step(PlanStep(
        step_id="process_form",
        agent_name="DataProcessor",
        instruction="Extract the core intent from the user query."
    ))

    # 5. Define Enterprise Context (Phase 9)
    # The presence of `data_region="RU"` triggers the 152-FZ compliance rule, 
    # forcing the system to NOT send PII to US-based servers and requires a local model route.
    context = {
        "data_region": "RU",
        "requires_local": True # Signal to the ModelRouter to pick `secure_local` (qwen2.5) instead of gpt-4
    }

    print("\n[Client] Sending user data with 'data_region=RU' context...")
    
    # 6. Execute (Will be intercepted by ComplianceEngine and ModelRouter)
    summary = await engine.execute(plan, context=context)
    
    print("\n[Result]")
    print(summary)


if __name__ == "__main__":
    asyncio.run(main())
