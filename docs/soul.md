# soul.md — SGR Kernel Design Decisions

> Read this before making architectural changes.
> Not a changelog. A distillation of why things are the way they are.
> Agents: read this at every session start, after `tree docs/`.

## Core identity

SGR Kernel is a **correctness layer**, not a framework.
Its job: *"Did this task execute exactly once, correctly, at the right time?"*
Speed and feature richness are secondary to that guarantee.

## Frozen decisions

### 1. Formal verification first
L8 invariants (Exclusivity, Bounded Duplication, Atomic Visibility, Progress)
are TLA+-verified. If a change breaks the TLA+ model, the implementation is wrong.

### 2. Lazy loading for skills
Heavy deps (Qdrant, PyTorch) are never imported at kernel startup.
Skills are plugins loaded on-demand via `skills/<name>/handler.py`.
A router failure should not take down PEFT.

### 3. Transfer via conversation history (not RPC)
Agent handoffs pass conversation history, not direct calls.
This makes the system interpretable, loggable, and rollback-safe.
Do not add agent-to-agent function calls — they bypass ACL and audit.

### 4. max_turns is a hard limit (default: 10)
Prevents infinite loops in swarm execution. Never remove it.

### 5. Compliance is structural
152-FZ, GDPR, HIPAA constraints live in the kernel, not in skills.
PII masking and audit trails happen regardless of which skill runs.

### 6. LLM agnosticism via litellm
Kernel never calls OpenAI/DeepSeek directly.
All LLM calls go through `litellm`, config is resolved at startup.
Provider cascade: Proxy → DeepSeek → Custom/Ollama.

### 7. Human-in-the-Loop is context-dependent
`approval_callback` is injected into CoreEngine at init:
- CLI: real console prompt (`input()`)
- API/Server: auto-approve (dangerous, but intentional for automation)
- Telegram: should use real human approval

This is a **deliberate asymmetry**, not a bug.

### 8. Documentation as inter-agent interface
`docs/` + `AGENTS.md` are the live contract between agent sessions.
When an agent discovers a non-obvious fact, it writes an `AICODE-NOTE` anchor
and updates `AGENTS.md` or `soul.md`. The next agent reads it — no human mediator.

ADRs (`docs/adr/`) are historical. They get stale and confuse LLMs.
`soul.md` is read at every session start and stays current.

### 9. Feature transfer via documents (not code copy-paste)
`Project A → document the feature → Project B → adapt from the document`
This keeps context alive, is more precise than cookiecutters, and is rollback-safe.

## Key tradeoffs

| Decision | Gave up | Why |
|---|---|---|
| TLA+ invariants | Experiment velocity | Correctness > speed |
| History-based Transfer | RPC performance | Auditability, rollback |
| Lazy skill loading | Simple imports | Isolation, fault tolerance |
| Kernel-level compliance | Skill dev speed | Regulatory is non-negotiable |
| Fail-open rate limiter | Strict throttling | Availability > protection |
| soul.md instead of ADR | Decision history | ADRs confuse LLMs, soul.md stays fresh |
| Document-first feature transfer | Speed of copy-paste | Context survives model resets |

## How things break (patterns to recognize)

- **New skill not showing in API** → `server.py` uses static imports, add it there too
- **Infinite agent loop** → `max_turns` might have been raised without limits — check
- **PII leak in response** → compliance logic was probably bypassed at skill level
- **HITL not triggering** → check which `approval_callback` was injected
- **Qdrant/Redis errors on startup** → `docker-compose up -d` first
- **replay() / fork() returns early** → no checkpoint saved yet; check `CheckpointManager`
- **Two CoreEngine instances clobbering each other** → `Container` is a class-level singleton

## What we are NOT

- Not a task queue (use Celery/Temporal for that)
- Not an LLM router (that's RouterAgent's job, not the kernel's)
- Not a RAG pipeline (that's KnowledgeAgent skill)
- Not opinionated about LLM provider
