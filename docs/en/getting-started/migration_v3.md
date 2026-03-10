# Migration Guide: SGR Kernel V2 → V3

This guide provides a clear path for enterprise clients migrating from SGR Kernel V2 (Monolith/Single-Agent) to V3 (Multi-Agent Swarm Enterprise Tier).

## Key Architectural Changes

1. **Decoupled State Management**
   - V2 relied on local memory and SQLite.
   - V3 uses a centralized **SwarmState** backed by Redis for multi-agent synchronization and distributed locks.
   - *Action*: Ensure `redis-server` is available and `REDIS_URL` is configured in your environment.

2. **From Single Agent to SwarmEngine**
   - V2 used a linear execution path.
   - V3 introduces the `SwarmEngine`, which routes tasks dynamically to specialized agents (`CriticEngine`, `Researcher`, etc.) based on intent and context.
   - *Action*: Update legacy `Kernel.run()` calls to initialize a `SwarmEngine` and submit tasks via `engine.execute()`.

3. **Enterprise Safeguards (New in V3)**
   - **Economic Layer**: All LLM calls are now intercepted by the `BudgetGuard`. You must explicitly provide an `economic_budget` in the session context, otherwise execution will fail with `BudgetExceededError`.
   - **Compliance Engine**: Data routing now checks against geographical/legal constraints (e.g., `152-FZ`). If processing sensitive data, ensure you request a `secure_local` model route.

## Step-by-Step Migration

1. **Update Infrastructure**
   Run the new Quickstart wizard:
   ```bash
   pwsh ./scripts/quickstart.ps1
   ```

2. **Update Code Dependencies**
   V3 introduces specific formal verification structures.
   ```python
   # Old V2 approach
   response = kernel.execute("Fix my code")
   
   # New V3 approach with Safeguards
   from core.swarm import SwarmEngine
   
   engine = SwarmEngine()
   # Provide safety constraints
   context = {
       "economic_budget": 0.50, # USD max
       "requires_local": True   # Forces local model via ModelRouter
   }
   response = await engine.execute(plan, context=context)
   ```

3. **Handling Verification Viloations**
   V3 enforces strict `OutputSpec` limits. If your downstream services expect specific JSON schemas, register them with the agent before execution to enable automated self-healing.
