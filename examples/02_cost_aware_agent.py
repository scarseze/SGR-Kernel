#!/usr/bin/env python3
"""
SGR Kernel V3 Enterprise Example: Cost-Aware Agent

This demonstrates the Phase 8 Economic Layer (TokenLedger & BudgetGuard) and Phase 11 Automated RCA.
It enforces a strict financial budget for an LLM task.
"""

import asyncio
import os
import sys

# Add parent dir to path to find core modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.agent import Agent
from core.execution import ExecutionPlan, PlanStep
from core.swarm import SwarmEngine


async def main():
    print("💰 Starting Cost-Aware Agent Demo")
    print("---------------------------------------")

    engine = SwarmEngine()

    # Create an agent that does heavy summarization (consumes many tokens)
    writer_agent = Agent(
        name="FinancialAnalyst",
        model="gpt-4-turbo",  # Expensive model
        instructions="Write a comprehensive, exhaustive 10-page thesis on market trends."
    )
    engine.register_agent(writer_agent)

    plan = ExecutionPlan(
        request_id="demo_budget_001",
        input_payload={"topic": "Global macroeconomic shifts in 2026"},
    )
    plan.add_step(PlanStep(
        step_id="analyze_markets",
        agent_name="FinancialAnalyst",
        instruction="Start generating the thesis."
    ))

    # Phase 8: Hard financial limit enforcement
    # We set an extremely low budget to intentionally trigger the BudgetGuard
    context = {
        "economic_budget": 0.001  # USD. gpt-4-turbo will almost certainly blow past this instantly.
    }

    print(f"\n[Client] Executing plan under strict ${context['economic_budget']} budget cap...")
    
    # Execute. This is expected to fail and automatically trigger Phase 11 RCA (Root Cause Analysis).
    summary = await engine.execute(plan, context=context)
    
    print("\n[Result / Auto-RCA]")
    print(summary)


if __name__ == "__main__":
    asyncio.run(main())
