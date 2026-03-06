#!/usr/bin/env python3
"""
SGR Kernel V3 Enterprise Example: High Availability (Blue-Green Swap)

This demonstrates Phase 12 ModelRouter and ContextDehydrator.
Simulates a primary LLM API outage and shows how the kernel seamlessly
fails over to a local model, compressing the conversation history if necessary.
"""

import asyncio
import os
import sys

# Add parent dir to path to find core modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.swarm import SwarmEngine
from core.agent import Agent
from core.execution import ExecutionPlan, PlanStep

async def simulate_outage(engine: SwarmEngine, model_id: str):
    print(f"\n⚠️ [SIMULATION] Simulating catastrophic outage for '{model_id}'...")
    if engine.model_router:
        engine.model_router.mark_down(model_id)
        print(f"⚠️ [SIMULATION] '{model_id}' status is DOWN.")

async def main():
    print("🔄 Starting High Availability Demo (Blue-Green Swap)")
    print("-------------------------------------------------")

    engine = SwarmEngine()
    
    # We'll use a generic agent, but the actual model used will be determined 
    # by the ModelRouter dynamically at runtime.
    resilient_agent = Agent(
        name="HA_Agent",
        instructions="You are a helpful assistant. Answer the user briefly."
    )
    engine.register_agent(resilient_agent)

    plan = ExecutionPlan(request_id="demo_ha_001", input_payload={"message": "Are you online?"})
    plan.add_step(PlanStep(step_id="step_1", agent_name="HA_Agent", instruction="Respond to the user."))

    print("\n[Client] First Execution (Expected: Primary Model 'gpt-4-turbo')")
    summary1 = await engine.execute(plan, context={})
    print(f"Result: {summary1.strip()}")

    # SIMULATE OUTAGE
    await simulate_outage(engine, "primary")

    print("\n[Client] Second Execution (Expected: Fallback Model with Zero Downtime)")
    plan2 = ExecutionPlan(request_id="demo_ha_002", input_payload={"message": "Are you still online?"})
    plan2.add_step(PlanStep(step_id="step_1", agent_name="HA_Agent", instruction="Respond to the user."))
    
    summary2 = await engine.execute(plan2, context={})
    print(f"Result: {summary2.strip()}")


if __name__ == "__main__":
    asyncio.run(main())
