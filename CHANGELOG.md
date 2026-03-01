# Changelog

All notable changes to this project will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [v3.0.0] - 2026-03-01 — Gold Master
### Added
- **Hierarchical Swarms** (`SubSwarmAgent`, `TransferToSubSwarm`): agents can now spawn nested swarms for infinite reasoning depth.
- **152-FZ Compliance**: `UIMemory` now enforces `.ru` DB residency, blocks foreign connections, and emits tamper-proof audit logs (HMAC).
- **GDPR / HIPAA**: Right-to-be-forgotten API (`delete_session`), PII masking for passports, SNILS, INN, credit cards, and phone numbers.
- **Mariana Trench Hardening**: Rate limiting, `/health/db` & `/health/swarm_topology` endpoints, input validation via `SecurityGuardian`, `STEP_FAILED` timeout events in scheduler.
- **PostgreSQL Persistence**: Full async SQLAlchemy + alembic support; deprecated SQLite for production.
- **Test Suite**: 126 tests passing, 9 skipped.

### Changed
- `SwarmEngine.execute()` now enforces `max_turns` (default 10) to prevent infinite agent loops.
- `MemoryManager` logging switched to f-strings to fix TypeError.

### Fixed
- `test_rf_152fz.py` environment variable teardown no longer leaks `MEMORY_DB_URL` across the test suite.
- `test_event_determinism`, `test_race_safety`, `test_replay_fork`, `test_replay_recon`: state loaded from checkpoints instead of cleared `active_executions`.

## [v2.1.0] - 2026-02-27 — Mariana Trench Hardening
### Added
- API rate limiting middleware in `server.py`.
- Cached health checks `/health/db` and `/health/swarm_topology`.
- `SecurityGuardian` input validation in the runtime loop.
- Explicit `STEP_FAILED` events on scheduler timeouts.

## [v2.0.0-rc1] - 2026-02-26
### Changed
- **Architecture Update**: The CoreEngine has been upgraded to a Multi-Agent Swarm architecture. The V1 DAG step-executor is now deprecated.
- **Agent Orchestration**: Introduced `RouterAgent`, `KnowledgeAgent`, `DataAgent`, `PeftAgent`, and `WriterAgent`.
- **Handoff Mechanism**: Added `TransferSkill` to allow agents to seamlessly transfer context and control via `context_summary` sanitization.
- **Loop Protection**: Implemented `max_transfers` in `SwarmEngine` to prevent infinite loops.
- **Observability**: Added WAL-style structured audit logging for handoffs.

## [v1.0.0] - Prior Release
### Added
- Initial release using monolithic DAG step-executor.
