# 7. Pre-Execution Plan Critic

Date: 2026-03-06

## Context

When an LLM agent decides to execute a powerful tool (e.g., `execute_sql_query`, `rewrite_system_prompt`), bad plans can lead to catastrophic data loss or infinite loops. Validating the result *after* the execution is often too late (e.g., dropping a table).

## Decision

The `CriticEngine` operates in two phases:
1. **Pre-Execution (Plan Critic)**: Before a tool is invoked, the Orchestrator checks the generated arguments against an ACL/Capability manifest and semantic guards.
2. **Post-Execution (Result Critic)**: After the tool returns, the output is formatted and checked for PII leaks or logic failures.

## Consequences

- **Pros**: Vastly increases the security surface area. Prevents destructive queries before they hit the database. Fits perfectly with our Adversarial Testing (Garak) methodology against Prompt Injection.
- **Cons**: Doubles the surface area for Critic invocations, somewhat increasing system latency.

## TLA+ Invariant Reference
```tla
Invariant: GuardBeforeEffect
  ∀ tool_call ∈ ToolCalls:
    Evaluated(tool_call) = TRUE ⟹ StateMutated = FALSE
```
