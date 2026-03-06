# 3. Human-in-the-Loop Escalation

Date: 2026-03-06

## Status

Accepted

## Context

The `CoreEngine` uses a `CriticEngine` to validate the semantic outputs of skill executions. If a skill output violates semantic requirements, it fails. The Orchestrator automatically retries failed steps. However, if a step repeatedly fails the Critic's checks (exhausting max attempts), the system previously aborted the execution, resulting in poor user experience and wasted compute resources, since a partial or "good enough" result might have been generated.

## Decision

We implemented a Human-in-the-Loop (HitL) escalation pattern:
1. When a step exhausts its retry attempts specifically due to a `CRITIC_FAIL`, the Execution Graph transitions from `RUNNING` to `PAUSED_APPROVAL`.
2. The Orchestrator publishes an `EXECUTION_PAUSED` event and halts.
3. A globally registered `approval_callback` is invoked, allowing a human operator (e.g., via the Telegram Bot UI) to review the partial output and the critic's rejection reason.
4. If approved intuitively, the state is forced to `COMMITTED` and execution resumes. Otherwise, it is `ABORTED`.

## Consequences

- **Pros**: Increases task completion rates. Prevents infinite looping and wasted LLM tokens. Allows human judgment to override overly strict programmatic critics.
- **Cons**: Introduces asynchronous blocking in the DAG. The orchestrator must handle prolonged pauses gracefully without holding database locks or timing out.
