# 6. SQLite for Local Checkpoints over In-Memory Redis

Date: 2026-03-06

## Context

As the SGR Kernel executes long-running Agent tasks (which may take hours and dozens of LLM calls), it generates a massive tree of conversational context, step history, and tool outputs. We need to store Checkpoint states securely to allow the `/rollback` feature to work.

## Decision

We chose **SQLite** (acting as a persistent disk-backed store for active sessions) to save full JSON-serialized `ExecutionState` blobs, rather than storing state fragments exclusively in Redis.

## Consequences

- **Pros**: 
  - Durability: Restarting the Kernel container does not wipe the state (since `memory.db` is volume mounted).
  - Trivial Checkpointing: We can perform simple relational lookups (`SELECT * FROM checkpoints WHERE session_id = ? ORDER BY step DESC LIMIT 1`) without complex keyspace schemas.
- **Cons**: Write throughput is lower than pure Redis. However, checkpointing occurs only at step boundaries, meaning disk I/O latency is negligible compared to massive LLM network API calls.

## TLA+ Invariant Reference
```tla
Invariant: StoragePersistence
  ∀ checkpoint ∈ Checkpoints:
    checkpoint is_durable = TRUE
```
