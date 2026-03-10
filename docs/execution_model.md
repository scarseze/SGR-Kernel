# SGR Kernel Swarm Execution Model (v3.x)

## Overview
The SGR Kernel acts as a deterministic **Correctness Layer** for autonomous multi-agent swarms. Unlike traditional DAG executors that follow a static pre-defined path, the Swarm Execution Model focuses on **dynamic turn-based orchestration**, autonomous hand-offs, and formal safety invariants.

## 1. The Swarm Loop
The execution follows a recursive **Prompt -> Execute -> Route** cycle:

1.  **Request**: User input and initial context are received.
2.  **Turn Initiation**: The `SwarmEngine` initializes the active agent (defaulting to `RouterAgent`).
3.  **Execution Cycle**:
    - **LLM Context Generation**: Active agent processes the history and generates a response or tool call.
    - **Capability Execution**: Skills (tools) are invoked through the `SkillLifecycleEngine`.
    - **Dynamic Routing (Handoff)**: If the agent decides to transfer control, a `TransferToAgent` event is emitted.
4.  **Verification**: The `CriticPolicy` validates the output. If rejected, a retry is triggered or human escalation occurs.
5.  **Checkpointing**: After every state mutation (turn), the `StateManager` persists the `ExecutionState` via Redis/SQLite.

## 2. Swarm State Machine
The execution state moves through dynamic phases:

| State | Description |
| :--- | :--- |
| `ACTIVE` | Swarm is currently processing a turn. |
| `WAITING_FOR_INPUT` | Execution paused, awaiting user response. |
| `PAUSED_APPROVAL` | Human-in-the-Loop: paused due to critic rejection or security flags. |
| `COMPLETED` | Swarm reached a terminal turn or successfully generated final answer. |
| `FAILED` | Terminal failure (e.g., budget exceeded, max turns reached). |
| `ABORTED` | Manually terminated by security policy or user. |

## 3. Data Flow & Handoffs
- **Turn Context**: History is passed between agents, serving as the "shared memory" of the swarm.
- **Handoffs**: Autonomous transfers of control that don't require a pre-defined graph (no DAG overhead).
- **Sanitization**: `ContextSanitizer` redacts sensitive data (PII) before passing context between agents or to the user.

## 4. Formal Guarantees
| Guarantee | Mechanism |
| :--- | :--- |
| **Atomic Visibility** | Results are only visible to the user after a successful state commit marker. |
| **Bounded Turns** | `max_turns` limit prevents infinite redirection loops in complex swarms. |
| **PII Protection** | Regex-based `ContextSanitizer` filters sensitive tokens during handoffs. |
| **Crash Recovery** | Automatic resumption from the last Turn Checkpoint in case of infrastructure failure. |
