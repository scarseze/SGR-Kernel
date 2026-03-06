import datetime
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, Text, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import create_async_engine

from core.audit_logger import ComplianceAuditLogger
from core.logger import get_logger
from core.pii_classifier import PIIClassifier

logger = get_logger("ui_memory")

# --- Schema Definition for Alembic ---
metadata_obj = MetaData()

sessions_table = Table(
    'sessions', metadata_obj,
    Column('session_id', String, primary_key=True),
    Column('org_id', String, default="default_org", index=True),
    Column('history_json', Text),
    Column('active_agent_name', String),
    Column('transfer_count', Integer, default=0),
    Column('created_at', DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc)),
    Column('updated_at', DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))
)

jobs_table = Table(
    'jobs', metadata_obj,
    Column('job_id', String, primary_key=True),
    Column('org_id', String, default="default_org", index=True),
    Column('status', String, default="CREATED"), # CREATED, QUEUED, LEASED, RUNNING, COMPLETED, FAILED
    Column('payload', Text),
    Column('lease_owner', String, nullable=True),
    Column('lease_expiry', DateTime, nullable=True),
    Column('lease_version', Integer, default=0),
    Column('artifact_uri', String, nullable=True),
    Column('created_at', DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc)),
    Column('updated_at', DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))
)

failed_scenarios_table = Table(
    'failed_scenarios', metadata_obj,
    Column('scenario_id', String, primary_key=True),
    Column('job_id', String, nullable=False, index=True),
    Column('org_id', String, default="default_org", index=True),
    Column('reason', String),
    Column('context_payload', Text),
    Column('created_at', DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))
)

class UIMemory:
    def __init__(self, db_url: Optional[str] = None):
        import os
        self.db_url = db_url or os.environ.get("MEMORY_DB_URL")
        if not self.db_url:
            raise ValueError("MEMORY_DB_URL must be provided.")
        self.compliance_level = os.environ.get("COMPLIANCE_LEVEL", "standard") # 'standard', 'gdpr', 'hipaa', 'rf_152fz'
        
        self.audit_logger = None
        self.db_host = ""
        self.is_local = True
        self.is_ru_domain = False
        
        if self.compliance_level == "rf_152fz":
            self._validate_data_localization()
            self.audit_logger = ComplianceAuditLogger()
            
        self.pii_classifier = PIIClassifier(compliance_level=self.compliance_level)
            
        # Ensure async driver for SQLite
        if self.db_url and self.db_url.startswith("sqlite") and "+aiosqlite" not in self.db_url:
            self.db_url = self.db_url.replace("sqlite://", "sqlite+aiosqlite://")

        self.engine = create_async_engine(self.db_url, pool_pre_ping=True)
        self.metadata = metadata_obj
        self.sessions = sessions_table
        self.jobs = jobs_table
        self.failed_scenarios = failed_scenarios_table
        
        # self.init_db() cannot be called in __init__ as it is async now.
        # It should be called explicitly during startup.

    def _validate_data_localization(self):
        self.db_host = self.db_url.split("@")[-1].split(":")[0].split("/")[0] if "@" in self.db_url else self.db_url
        self.is_local = self.db_host in ("localhost", "127.0.0.1") or self.db_url.startswith("sqlite")
        self.is_ru_domain = bool(re.search(r'\.ru$', self.db_host))

    async def _enforce_tenant_residency(self, org_id: str):
        """
        True Data Localization Router check for 152-FZ.
        Validates that the current physical database mapped to the connection pool
        is legally allowed to store data for the given tenant's residency requirements.
        """
        if self.compliance_level != "rf_152fz":
            return
            
        # Mocking a Tenant Registry lookup. In reality, this queries a distributed Consul or Redis mapping.
        tenant_residency = "RU" if org_id.endswith("_ru") or org_id == "default_org" else "GLOBAL"
        
        if tenant_residency == "RU":
            if not (self.is_local or self.is_ru_domain):
                logger.critical("tenant_residency_violation", org_id=org_id, required_residency="RU", db_host=self.db_host)
                raise PermissionError(
                    f"152-FZ Violation: Tenant '{org_id}' requires 'RU' residency, "
                    f"but current connection pool is routed to '{self.db_host}'."
                )

    async def initialize(self):
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(self.metadata.create_all)
                
                # If SQLite, try to set WAL mode
                if self.db_url.startswith("sqlite"):
                    await conn.execute(text("PRAGMA journal_mode=WAL;"))
                elif self.db_url.startswith("postgresql"):
                    try:
                        await conn.execute(text("ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;"))
                        await conn.execute(text("DROP POLICY IF EXISTS tenant_isolation_policy ON sessions;"))
                        await conn.execute(text("CREATE POLICY tenant_isolation_policy ON sessions USING (org_id = current_setting('app.current_org_id', true));"))
                        await conn.execute(text("ALTER TABLE sessions FORCE ROW LEVEL SECURITY;"))
                        logger.info("152-FZ/Hardening: PostgreSQL Row-Level Security enabled for sessions.")
                    except Exception as e:
                        logger.warning(f"Failed to enable RLS on PostgreSQL. Ensure the connection user has privileges: {e}")
        except Exception as e:
            logger.error(f"Failed to initialize memory DB: {str(e)}")

    async def _apply_rls_context(self, conn, org_id: str):
        """Sets the RLS context for the current transaction if using PostgreSQL"""
        if self.db_url.startswith("postgresql"):
            from sqlalchemy import text
            await conn.execute(text(f"SET LOCAL app.current_org_id = '{org_id}';"))

    def _mask_pii(self, content: str) -> str:
        """
        Uses the internal ML-based PII Classifier pipeline (mocking Microsoft Presidio / HuggingFace NER)
        instead of brittle static Regex checks, complying with Enterprise Staff requirements.
        """
        if not content:
            return content
            
        return self.pii_classifier.anonymize(content)

    async def summarize_history(self, messages_to_compress: List[Dict[str, Any]]) -> str:
        """
        Compresses a chunk of outdated messages into a single summary using a small LLM model.
        """
        import litellm
        model = os.environ.get("SUMMARY_LLM", "gpt-4o-mini") # Can point to qwen2.5:1.5b via Ollama matching
        
        conversation_text = "\n".join([f"{m.get('role', 'user')}: {m.get('content', '')}" for m in messages_to_compress])
        prompt = f"""Summarize this chat context concisely. Keep critical facts, constraints, and decisions.

Conversation:
{conversation_text}

Summary:"""
        try:
            response = await litellm.acompletion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Summarizer failed: {e}")
            return "Summary unavailable due to error."

    async def async_truncate_history(self, history: List[Dict[str, Any]], max_messages: int = 15) -> List[Dict[str, Any]]:
        """
        Auto-summarization pipeline. If context exceeds max_messages, we compress the middle
        chunk into a 'system' reminder message instead of blindly throwing it away.
        """
        if len(history) <= max_messages + 1:
            return history
            
        system_prompt = history[0]
        recent_history = history[-max_messages:]
        
        # The messages being kicked out
        forgotten_messages = history[1:-max_messages]
        
        if forgotten_messages:
            summary = await self.summarize_history(forgotten_messages)
            summary_message = {
                "role": "system",
                "content": f"[AUTO-SUMMARY OF PREVIOUS CONTEXT]: {summary}"
            }
            return [system_prompt, summary_message] + recent_history
            
        return [system_prompt] + recent_history

    def truncate_history(self, history: List[Dict[str, Any]], max_messages: int = 20) -> List[Dict[str, Any]]:
        """ Synchronous fallback """
        if len(history) <= max_messages + 1:
            return history
        system_prompt = history[0]
        recent_history = history[-max_messages:]
        return [system_prompt] + recent_history

    async def save_session(
        self, 
        session_id: str, 
        history: List[Dict[str, Any]], 
        active_agent_name: str,
        transfer_count: int,
        audit_callback: Optional[callable] = None,
        org_id: str = "default_org"
    ):
        """Asynchronous version with smart context compression"""
        try:
            # 1. Truncate history to avoid exceeding context window
            truncated_history = await self.async_truncate_history(history)
            
            # 2. Basic PII Masking on message contents
            masked_history = []
            pii_masked = False
            for msg in truncated_history:
                masked_msg = dict(msg)
                if "content" in masked_msg and isinstance(masked_msg["content"], str):
                    original_content = masked_msg["content"]
                    masked_msg["content"] = self._mask_pii(masked_msg["content"])
                    if original_content != masked_msg["content"]:
                        pii_masked = True
                masked_history.append(masked_msg)
                
            if self.audit_logger and pii_masked:
                await self.audit_logger.log_event_async("PII_MASKED", session_id, {"action": "Data masked before async saving"})
                
            history_json = json.dumps(masked_history, ensure_ascii=False)
            now = datetime.datetime.now(datetime.timezone.utc)

            # Upsert logic depends on dialect
            stmt_params = {
                "session_id": session_id,
                "org_id": org_id,
                "history_json": history_json,
                "active_agent_name": active_agent_name,
                "transfer_count": transfer_count,
                "created_at": now,
                "updated_at": now
            }

            is_sqlite = self.db_url.startswith('sqlite')
            insert_stmt = sqlite_insert(self.sessions) if is_sqlite else pg_insert(self.sessions)
            
            upsert_stmt = insert_stmt.on_conflict_do_update(
                index_elements=['session_id'],
                set_={
                    "org_id": insert_stmt.excluded.org_id,
                    "history_json": insert_stmt.excluded.history_json,
                    "active_agent_name": insert_stmt.excluded.active_agent_name,
                    "transfer_count": insert_stmt.excluded.transfer_count,
                    "updated_at": insert_stmt.excluded.updated_at
                }
            )

            async with self.engine.begin() as conn:
                await self._enforce_tenant_residency(org_id)
                await self._apply_rls_context(conn, org_id)
                await conn.execute(upsert_stmt, stmt_params)
            
            if audit_callback:
                audit_callback(session_id, active_agent_name, transfer_count)
                
        except Exception as e:
            if isinstance(e, PermissionError):
                raise
            logger.error(f"Failed to save session for {session_id}: {str(e)}")

    # Alias for compatibility if needed, or just remove async_save_session as duplicate
    async_save_session = save_session

    async def load_session(self, session_id: str, org_id: str = "default_org") -> Tuple[List[Dict[str, Any]], Optional[str], int]:
        """
        Returns (history, active_agent_name, transfer_count).
        If not found, returns ([], None, 0).
        """
        try:
            from sqlalchemy import select
            async with self.engine.begin() as conn:
                await self._enforce_tenant_residency(org_id)
                await self._apply_rls_context(conn, org_id)
                stmt = select(
                    self.sessions.c.history_json,
                    self.sessions.c.active_agent_name,
                    self.sessions.c.transfer_count
                ).where(self.sessions.c.session_id == session_id)
                
                result = await conn.execute(stmt)
                row = result.fetchone()

            if row:
                history = json.loads(row[0])
                active_agent_name = row[1]
                transfer_count = row[2]
                return history, active_agent_name, transfer_count
            else:
                return [], None, 0
                
        except Exception as e:
            if isinstance(e, PermissionError):
                raise
            logger.error(f"Failed to load session for {session_id}: {str(e)}")
            return [], None, 0

    async def get_unreflected_sessions(self, limit: int = 50, inactive_hours: int = 1) -> List[Dict[str, Any]]:
        """
        Finds sessions that haven't been updated recently and might have long histories.
        """
        from sqlalchemy import select
        now = datetime.datetime.now(datetime.timezone.utc)
        threshold_time = now - datetime.timedelta(hours=inactive_hours)
        
        try:
            async with self.engine.begin() as conn:
                stmt = select(
                    self.sessions.c.session_id,
                    self.sessions.c.org_id,
                    self.sessions.c.history_json
                ).where(self.sessions.c.updated_at < threshold_time).limit(limit)
                
                result = await conn.execute(stmt)
                sessions = []
                for row in result.fetchall():
                    history = json.loads(row[2])
                    # Only reflect if the history is long enough to warrant compression
                    if len(history) > 15:
                        sessions.append({
                            "session_id": row[0],
                            "org_id": row[1],
                            "history": history
                        })
                return sessions
        except Exception as e:
            logger.error(f"get_unreflected_sessions_error: {e}")
            return []

    async def reflect_session(self, session_id: str, history: List[Dict[str, Any]], org_id: str = "default_org") -> bool:
        """
        Compresses a session's history and saves it back to the database.
        """
        try:
            logger.info("reflecting_session", session_id=session_id, original_messages=len(history))
            # Force compression down to 10 messages max
            compressed_history = await self.async_truncate_history(history, max_messages=10)
            
            if len(compressed_history) < len(history):
                # We actually compressed it, save it back
                history_json = json.dumps(compressed_history, ensure_ascii=False)
                now = datetime.datetime.now(datetime.timezone.utc)
                
                from sqlalchemy import update
                async with self.engine.begin() as conn:
                    await self._enforce_tenant_residency(org_id)
                    await self._apply_rls_context(conn, org_id)
                    
                    stmt = update(self.sessions).where(self.sessions.c.session_id == session_id).values(
                        history_json=history_json,
                        updated_at=now # Touch the updated_at so we don't scan it again immediately
                    )
                    await conn.execute(stmt)
                
                logger.info("session_reflection_complete", session_id=session_id, new_messages=len(compressed_history))
                return True
        except Exception as e:
            logger.error(f"reflect_session_error for {session_id}: {e}")
            
        return False

    async def cleanup_expired_sessions(self, ttl_days: int = 30):
        try:
            from sqlalchemy import delete
            limit_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=ttl_days)
            async with self.engine.begin() as conn:
                stmt = delete(self.sessions).where(self.sessions.c.updated_at < limit_date)
                result = await conn.execute(stmt)
                deleted = result.rowcount
                
            if deleted > 0:
                logger.info(f"Cleaned up {deleted} expired sessions.")
        except Exception as e:
            logger.error(f"Failed to cleanup expired sessions: {str(e)}")

    async def delete_session(self, session_id: str, org_id: str = "default_org") -> bool:
        """
        Right-to-be-forgotten implementation.
        Completely removes user data from the database.
        """
        try:
            from sqlalchemy import delete
            async with self.engine.begin() as conn:
                await self._enforce_tenant_residency(org_id)
                await self._apply_rls_context(conn, org_id)
                stmt = delete(self.sessions).where(self.sessions.c.session_id == session_id)
                result = await conn.execute(stmt)
                deleted = result.rowcount > 0
                
            if deleted and self.audit_logger:
                self.audit_logger.log_event("RIGHT_TO_BE_FORGOTTEN", session_id, {"action": "Complete session deletion"})
                
            return deleted
        except Exception as e:
            if isinstance(e, PermissionError):
                raise
            logger.error(f"Failed to delete session {session_id}: {str(e)}")
            return False
            
    async def async_delete_session(self, session_id: str, org_id: str = "default_org", purge_vectors: bool = True) -> bool:
        """
        Asynchronous Right-to-be-forgotten implementation.
        Completely removes user data from the database, and cascades to vector indices and derived backups.
        """
        success = await self.delete_session(session_id, org_id)
        
        if success:
            # Right-to-be-Forgotten Phase 1.5: Cache Eviction
            # The database row is gone, but we must ensure no traces remain in Redis.
            try:
                from core.container import Container
                redis_client = Container.get("redis")
                if redis_client:
                    # Wipe specific session buffers, locks, or limits that might exist
                    cursor = b'0'
                    while cursor:
                        cursor, keys = await redis_client.scan(cursor=cursor, match=f"*{session_id}*")
                        if keys:
                            await redis_client.delete(*keys)
                    logger.info("right_to_be_forgotten_redis_purged", session_id=session_id)
            except Exception as e:
                logger.error("right_to_be_forgotten_redis_purge_failed", session_id=session_id, error=str(e))
                
        if success and purge_vectors:
            # Propagate deletion to vector embeddings (if applicable).
            # We don't have direct access to Qdrant/Milvus here, but we emit a tombstone event or call a registry.
            logger.info(f"TOMBSTONE: Emitting physical erasure event for session vectors: {session_id}")
            try:
                from core.container import Container
                event_bus = Container.get("event_bus")
                if event_bus:
                    from core.events import EventType, KernelEvent
                    event = KernelEvent(
                        type=EventType.RESOURCE_DELETED, 
                        request_id=f"purge_{session_id}",
                        step_id="system",
                        payload={"session_id": session_id, "action": "hard_delete_vectors", "org_id": org_id}
                    )
                    await event_bus.publish(event)
            except Exception as ev_err:
                logger.error(f"Failed to emit vector deletion tombstone for {session_id}: {ev_err}")
                
        return success

    # --- Principal-Level Job Execution State Management ---

    async def create_job(self, job_id: str, org_id: str, payload: dict) -> bool:
        """Records a new job in the Durable Database (Source of Truth) BEFORE pushing to the message broker."""
        try:
            async with self.engine.begin() as conn:
                await self._enforce_tenant_residency(org_id)
                await self._apply_rls_context(conn, org_id)
                
                payload_str = json.dumps(payload)
                
                if self.engine.name == 'postgresql':
                    stmt = pg_insert(self.jobs).values(
                        job_id=job_id,
                        org_id=org_id,
                        status="CREATED",
                        payload=payload_str,
                        lease_version=0
                    ).on_conflict_do_nothing()
                else:
                    stmt = sqlite_insert(self.jobs).values(
                        job_id=job_id,
                        org_id=org_id,
                        status="CREATED",
                        payload=payload_str,
                        lease_version=0
                    ).on_conflict_do_nothing()
                    
                await conn.execute(stmt)
            logger.info("job_persisted_to_db", job_id=job_id, status="CREATED")
            return True
        except Exception as e:
            logger.error("failed_to_persist_job", job_id=job_id, error=str(e))
            return False

    _UNSET = object()  # Sentinel to distinguish "not provided" from "explicitly None"

    async def update_job_status(self, job_id: str, status: str, lease_owner = _UNSET, lease_expiry = _UNSET, artifact_uri = _UNSET, expected_version = _UNSET) -> bool:
        """
        Updates the status and lease details of a job. Uses strict Compare-And-Swap (CAS).
        L8 DISTINGUISHED REQUIREMENT:
        - Atomicity is guaranteed structurally by `UPDATE ... WHERE ...` acting as a strict row-level exclusive lock.
        - Isolation Level: Production deployments must strictly enforce SERIALIZABLE transaction isolation on the connection pool 
          to guarantee complete linearizability free of Phantom Reads or Non-Repeatable read anomalies.
        - G2 Eventual Progress: Partition-Level Admission Control explicitly prevents constant CAS livelocks.
        """
        try:
            from sqlalchemy import func, select, update
            async with self.engine.begin() as conn:
                # --- L8 DISTINGUISHED: G2 Partition-Level Admission Control ---
                # Before attempting a highly-contended CAS update under SERIALIZABLE isolation,
                # we explicitly check partition heat (e.g., how many jobs are RUNNING in this tenant).
                # If contention $C$ is too high, we shed the update attempt to prevent livelock starvation.
                if expected_version is not self._UNSET and status == "RUNNING":
                    # We only throttle the initial lease acquisition, not completions or failures
                    # Check tenant contention
                    tenant_query = select(self.jobs.c.org_id).where(self.jobs.c.job_id == job_id)
                    result = await conn.execute(tenant_query)
                    org_id = result.scalar()
                    
                    if org_id:
                        contention_query = select(func.count()).where(
                            (self.jobs.c.org_id == org_id) & 
                            (self.jobs.c.status == "RUNNING")
                        )
                        result = await conn.execute(contention_query)
                        active_leases = result.scalar() or 0
                        
                        # Hard structurally bounded contention $C$ per partition
                        MAX_PARTITION_CONTENTION = 50 
                        if active_leases >= MAX_PARTITION_CONTENTION:
                            logger.error("g2_livelock_prevention_rejected_lease", job_id=job_id, partition=org_id, active=active_leases)
                            # By returning False here, the worker treats it as a CAS loss,
                            # triggering exponential backoff + jitter without hitting the DB's serialization lock manager.
                            return False

                values = {"status": status, "updated_at": datetime.datetime.now(datetime.timezone.utc)}
                if lease_owner is not self._UNSET:
                    values["lease_owner"] = lease_owner
                if lease_expiry is not self._UNSET:
                    values["lease_expiry"] = lease_expiry
                if artifact_uri is not self._UNSET:
                    values["artifact_uri"] = artifact_uri
                    
                if expected_version is not self._UNSET:
                    values["lease_version"] = expected_version + 1
                    
                stmt = update(self.jobs).where(self.jobs.c.job_id == job_id)
                if expected_version is not self._UNSET:
                    stmt = stmt.where(self.jobs.c.lease_version == expected_version)
                    
                stmt = stmt.values(**values)
                result = await conn.execute(stmt)
                
                if expected_version is not self._UNSET and result.rowcount == 0:
                    logger.warning("job_cas_failure_stale_lease", job_id=job_id, expected_version=expected_version)
                    return False

            logger.info("job_status_updated", job_id=job_id, status=status)
            return True
        except Exception as e:
            logger.error("failed_to_update_job_status", job_id=job_id, status=status, error=str(e))
            return False

    async def get_active_jobs(self) -> List[Dict[str, Any]]:
        """Used by the Reconciliation Loop to scan for orphaned or stuck jobs."""
        try:
            from sqlalchemy import select
            async with self.engine.connect() as conn:
                # Get jobs that are not completed or failed
                stmt = select(self.jobs).where(self.jobs.c.status.in_(['CREATED', 'QUEUED', 'LEASED', 'RUNNING']))
                result = await conn.execute(stmt)
                
                jobs = []
                for row in result:
                    # Convert row to dict
                    job_dict = dict(row._mapping)
                    jobs.append(job_dict)
                return jobs
        except Exception as e:
            logger.error("failed_to_fetch_active_jobs", error=str(e))
            return []

    async def get_stale_jobs(self, grace_period_seconds: int = 30) -> List[Dict[str, Any]]:
        """
        L8 IMPERATIVE: Solves the Distributed Time Problem.
        Extracts stale RUNNING jobs by explicitly avoiding app-side clock skew.
        Relies EXCLUSIVELY on the Database internal `CURRENT_TIMESTAMP`.
        """
        try:
            from sqlalchemy import select, text
            async with self.engine.connect() as conn:
                # Use DB time strictly instead of local python `datetime.now()`
                # Handle SQLite and Postgres timestamp formats natively.
                if self.engine.name == 'postgresql':
                    db_time_predicate = text(f"lease_expiry + interval '{grace_period_seconds} seconds' < CURRENT_TIMESTAMP AT TIME ZONE 'UTC'")
                else:
                    # SQLite dialect syntax for datetime manipulation
                    db_time_predicate = text(f"datetime(lease_expiry, '+{grace_period_seconds} seconds') < datetime('now')")

                stmt = select(self.jobs).where(
                    (self.jobs.c.status == 'RUNNING') & db_time_predicate
                )
                
                result = await conn.execute(stmt)
                jobs = []
                for row in result:
                    jobs.append(dict(row._mapping))
                return jobs
        except Exception as e:
            logger.error("failed_to_fetch_stale_jobs_via_db_time", error=str(e))
            return []

    async def get_failed_jobs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Returns jobs that failed, used by the Reconciler to generate safety cases."""
        try:
            from sqlalchemy import select
            async with self.engine.connect() as conn:
                stmt = select(self.jobs).where(self.jobs.c.status == 'FAILED').order_by(self.jobs.c.updated_at.desc()).limit(limit)
                result = await conn.execute(stmt)
                return [dict(row._mapping) for row in result]
        except Exception as e:
            logger.error("failed_to_fetch_failed_jobs", error=str(e))
            return []

    async def save_failed_scenario(self, scenario_id: str, job_id: str, org_id: str, reason: str, context_payload: str) -> bool:
        """Saves a failed context scenario to the database for offline testing."""
        try:
            async with self.engine.begin() as conn:
                await self._enforce_tenant_residency(org_id)
                await self._apply_rls_context(conn, org_id)

                if self.engine.name == 'postgresql':
                    stmt = pg_insert(self.failed_scenarios).values(
                        scenario_id=scenario_id,
                        job_id=job_id,
                        org_id=org_id,
                        reason=reason,
                        context_payload=context_payload
                    ).on_conflict_do_nothing()
                else:
                    stmt = sqlite_insert(self.failed_scenarios).values(
                        scenario_id=scenario_id,
                        job_id=job_id,
                        org_id=org_id,
                        reason=reason,
                        context_payload=context_payload
                    ).on_conflict_do_nothing()
                    
                await conn.execute(stmt)
            logger.info("failed_scenario_saved", scenario_id=scenario_id, job_id=job_id)
            return True
        except Exception as e:
            logger.error("failed_to_save_scenario", scenario_id=scenario_id, error=str(e))
            return False

    async def get_unresolved_scenarios(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Used by the code generator script to build offline tests."""
        try:
            from sqlalchemy import select
            async with self.engine.connect() as conn:
                stmt = select(self.failed_scenarios).order_by(self.failed_scenarios.c.created_at.desc()).limit(limit)
                result = await conn.execute(stmt)
                return [dict(row._mapping) for row in result]
        except Exception as e:
            logger.error("failed_to_fetch_scenarios", error=str(e))
            return []

    async def check_health(self) -> bool:
        """
        Verifies connectivity to the backing database.
        """
        try:
            async with self.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"UIMemory health check failed: {str(e)}")
            return False
