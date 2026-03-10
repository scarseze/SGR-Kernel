# AGENTS.md — SGR Kernel Navigation Guide

> This file is for AI agents. Read it first. Humans: see README.md instead.
> This is a **living inter-agent contract**, not human documentation.
> When one agent writes a finding here, the next picks it up — no human mediator needed.

## What this is

SGR Kernel is an Agentic OS — a **correctness layer** for multi-agent swarms.
It guarantees deterministic, exactly-once execution where standard orchestrators
(K8s, Temporal) only guarantee delivery.

Stack: Python 3.10+, Redis (state/rate-limit), Qdrant (vector memory),
Docker (infra), Chainlit (WebUI), Aiogram (Telegram), FastAPI (API server).

## Start here

```bash
tree docs/
grep -r "AICODE-" --include="*.py" .
```

Then read [docs/soul.md](docs/soul.md) — frozen design decisions.

## Three knowledge layers (read in order)

| Layer | What | Rule |
|---|---|---|
| `KERNEL_SPEC.md` | Ground truth: TLA+-verified invariants | Read-only, never change |
| `docs/` + this file | Current state — authoritative | Always read `tree docs/` first |
| `docs/adr/` + RFC history | Past decisions | Only if explicitly needed, marked stale |

**Protocol:** Always run `tree docs/` at session start. Never skip it.

## Where to find what

| What | Where |
|---|---|
| Execution guarantees & invariants | [KERNEL_SPEC.md](KERNEL_SPEC.md) |
| Agent architecture & flow | [docs/architecture.md](docs/architecture.md) |
| Frozen design decisions | [docs/soul.md](docs/soul.md) |
| Core engine (SwarmEngine, routing, middleware) | `core/` |
| Skill plugins | `skills/` |
| Tests | `tests/` |
| Infra (Redis, Qdrant, Jaeger, Grafana, Optuna) | `docker-compose*.yml` |

## Entry points — 4 run modes

```bash
python main.py              # CLI console (default)
python main.py --telegram   # Telegram bot via Aiogram
python main.py --server     # FastAPI on :8000
chainlit run ui_app.py      # Chainlit WebUI
```

## LLM provider cascade

`main.py` resolves LLM config in this priority order:
1. `PROXY_URL` env → Security Proxy (recommended)
2. `DEEPSEEK_API_KEY` env → Direct DeepSeek (labeled INSECURE in code)
3. `LLM_BASE_URL` + `LLM_API_KEY` + `LLM_MODEL` → Custom/Ollama

> ⚠️ `server.py` does NOT implement the full cascade from `main.py`.
> It only checks `DEEPSEEK_API_KEY`. If you add a new provider to `main.py`,
> update `server.py` `startup_event()` as well.

Kernel is LLM-agnostic; all calls go through `litellm`.

## Skill loading

| Entry point | Loading strategy |
|---|---|
| `main.py` | Dynamic: `skills.loader.load_skills(engine)` |
| `server.py` | Static: hardcoded imports + `engine.register_skill()` |

Skills live in `skills/<name>/handler.py`. Current skills:
SGLang, Portfolio, GostWriter, Calendar, RLM, WebSearch,
Office, DataAnalyst, ResearchAgent, Filesystem, LogicRL, PEFTlab.

**When adding a new skill — update BOTH entry points.**

## Infrastructure (docker-compose)

| Service | Port | Purpose |
|---|---|---|
| Redis | 6379 | State, rate-limiting |
| Qdrant | 6333 | Vector memory for RAG |
| Jaeger | 16686 | Distributed tracing |
| Optuna Dashboard | 8080 | HPO monitoring for PEFTlab |

Additional compose files: `docker-compose.dev.yml`, `docker-compose.chaos.yml`,
`docker-compose.indexer.yml`.

## Anchor comments

- `AICODE-NOTE:` — non-obvious design decisions
- `AICODE-TODO:` — known gaps, future work
- `AICODE-QUESTION:` — things that might be wrong

Before scanning files, grep first: `grep -r "AICODE-" --include="*.py" .`
After finishing any task, add at least one anchor if you learned something non-obvious.
Full anchor catalogue: [refs/anchor_comments.md](refs/anchor_comments.md)

## Do not touch

- L8 invariants in [KERNEL_SPEC.md](KERNEL_SPEC.md) — TLA+-verified
- ACL enforcement in middleware — never skip or stub in non-test code
- Output sanitization before user-facing responses
- `approval_callback` param in CoreEngine — it's how HITL works
- LLM provider cascade order in `main.py` — intentional priority
- `max_turns` limit — prevents infinite swarm loops

## Known gotchas

- `server.py` auto-approves all HITL actions (`api_approval` returns True).
  Do not copy this pattern to Telegram or CLI — they need real human approval.
- `server.py` hardcodes skill imports while `main.py` uses dynamic loader.
  New skills should work in both — test both paths.
- Rate limiter in `server.py` uses Redis. If Redis is down, it silently passes.
  This is intentional (fail-open) but worth knowing.
- `Container` uses class-level dicts — it's a process-wide singleton.
  Two `CoreEngine` instances will clobber each other's registrations.
- `replay()` and `fork()` re-execute from checkpoint, not from live state.
  If no checkpoint exists they return early — ensure checkpoints are enabled.
- `abort()` sets `ExecutionStatus.ABORTED` directly on state dict — it does not
  publish a `KernelEvent`. Orchestrator checks status flag, not event log.

## Feature transfer pattern

When porting a feature from another project:
1. Document the feature in `docs/` (source of truth)
2. Adapt from the document — not from raw code copy-paste
3. This keeps the context alive across agent sessions

## Modifying docs

- `docs/` — internal notes (authoritative)
- `docs/en/` + `docs/ru/` — public-facing (bilingual)
- Keep `docs/soul.md` updated when making design decisions
- Keep this file roughly same length — add and remove together
