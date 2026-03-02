# 📜 Swarm Protocol Specification
**Protocol Version:** 1.0

## 1. 🤝 Handoff Protocol
The SGR Kernel V2 leverages a multi-agent swarm architecture. Agents do not call each other directly via function calls. Instead, they yield a `TransferToAgent` object via the `TransferSkill`.

When an Agent yields control, it **must** provide a `context_summary` outlining:
- The user's original intent.
- Any intermediate discoveries.
- The specific reason why the control is being transferred to the new Agent.

## 2. 🛡️ Context Sanitization (Bleed Protection)
To prevent prompt injection and context bloat, the `SwarmEngine` intercepts the handoff and **re-writes the message history** for the incoming agent.
The new agent receives:
1. Its own `system` instructions.
2. A single `user` message containing the `[Context from PreviousAgent]: <context_summary>`.

This ensures PII and verbose thought processes from prior agents do not pollute the current agent's context window.

## 3. 🔄 Loop Protection
The `SwarmEngine` enforces a strict `max_transfers` limit (default: 5) per session turn. If agents ping-pong requests back and forth infinitely, the engine will intercept the 6th transfer and return an escalation error to the user.

## 4. 🗃️ Audit Logging (WAL)
Every successful handoff triggers a structured log entry under the `transfer_audit` tag, including:
- `from_agent`
- `to_agent`
- `context`
This allows full traceability of swarm decisions in production environments.
