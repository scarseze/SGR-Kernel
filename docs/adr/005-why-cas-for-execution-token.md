# 5. Compare-And-Swap (CAS) for Execution Tokens

Date: 2026-03-06

## Context

In a distributed Swarm, multiple worker nodes may attempt to execute the same intermediate step in the Execution Graph if a network partition or prolonged pause triggers a retry. The orchestrator must prevent duplicate side-effects (e.g., sending two identical emails or querying the DB twice for the exact same transaction).

## Decision

We use an atomic `SETNX` (Compare-And-Swap) mechanism in Redis to acquire an `ExecutionToken` (`step_id:run_id`).
1. A worker attempts to acquire the lease with a bounded TTL.
2. If `SETNX` returns False, another worker is actively executing the step; this worker backs off and skips the step.
3. The lease must be explicitly released only upon successful state transition (Commit).

## Consequences

- **Pros**: Guarantees At-Most-Once processing within the TTL window. Prevents concurrent execution collisions exactly as mandated by the `S3CommitProtocol.tla`.
- **Cons**: If a worker crashes mid-execution, the step is locked until the TTL expires, leading to a temporary latency spike until the lease timeout.

## TLA+ Invariant Reference
```tla
Invariant: Exclusivity
  ∀ step ∈ Tasks:
    Cardinality({w ∈ Workers: w is_executing step}) ≤ 1
```
