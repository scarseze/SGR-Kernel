import asyncio
import json
import structlog
import datetime
from typing import Optional
from core.container import Container
from core.distributed_lock import DistributedLock

logger = structlog.get_logger(__name__)

class BackgroundReconciler:
    """
    Principal-level System Component: The Reaper (Reconciliation Loop).
    Ensures that if workers die mid-execution or events are lost in the stream,
    the system eventually reaches a consistent terminal state (Requeue or Failsafe).
    Uses Distributed Lock to ensure 10 Orchestrators don't all run this loop simultaneously.
    """
    def __init__(self, scan_interval_seconds: int = 60):
        self.scan_interval = scan_interval_seconds
        self.leader_lock = DistributedLock("reconciler_loop", lock_timeout_ms=15000)
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def start(self):
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._run_loop())
            logger.info("reconciler_started", interval=self.scan_interval)

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self.leader_lock.is_leader:
            await self.leader_lock.release()
        logger.info("reconciler_stopped")

    async def _run_loop(self):
        while self._running:
            try:
                # 1. Attempt Leader Election (to prevent Split-Brain Reconciliations)
                if not self.leader_lock.is_leader:
                    acquired = await self.leader_lock.acquire_and_hold()
                    if not acquired:
                        # We lost the election. Sleep and try again later.
                        await asyncio.sleep(self.scan_interval)
                        continue

                # We are the Leader. Run the sweep.
                await self._sweep_orphaned_jobs()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("reconciler_sweep_error", error=str(e))
                
            await asyncio.sleep(self.scan_interval)

    async def _sweep_orphaned_jobs(self):
        """Scans for jobs stuck in RUNNING state whose lease has expired using DB Source of Truth."""
        ui_memory = Container.get("ui_memory")
        if not ui_memory:
            logger.warning("reconciler_sweep_skipped_no_db")
            return

        logger.info("reconciler_db_sweep_started")
        
        try:
            active_jobs = await ui_memory.get_active_jobs()
            now = datetime.datetime.now(datetime.UTC)
            
            # 1. Sweep stale RUNNING jobs strictly using DB-side clocks (Solves Distributed Time)
            stale_jobs = await ui_memory.get_stale_jobs(grace_period_seconds=30)
            for job in stale_jobs:
                job_id = job.get("job_id")
                logger.warning("orphaned_job_detected_db", job_id=job_id, status="RUNNING_LEASE_EXPIRED")
                await self._recover_orphaned_job(job_id, job, ui_memory)
                
            # 2. Handle CREATED jobs that stuck before hitting Queue (Redis failure)
            active_jobs = await ui_memory.get_active_jobs()
            now = datetime.datetime.now(datetime.UTC)
            for job in active_jobs:
                job_id = job.get("job_id")
                status = job.get("status")
                
                # G1 Guarantee: CREATED jobs that were never enqueued
                if status == "CREATED":
                    created_at = job.get("created_at")
                    if created_at:
                        age_naive = created_at.replace(tzinfo=None) if created_at.tzinfo else created_at
                        now_naive = now.replace(tzinfo=None)
                        if (now_naive - age_naive).total_seconds() > 120:
                            logger.warning("stuck_created_job_detected", job_id=job_id)
                            await self._recover_orphaned_job(job_id, job, ui_memory)
        except Exception as e:
            logger.error("reconciler_db_sweep_error", error=str(e))

    async def _recover_orphaned_job(self, job_id: str, job_record: dict, ui_memory):
        """
        The "Principal-Level Recovery Scenario" (Formal Guarantee G1 preserved)
        If a worker died on RUNNING -> Lease expires -> Reconciliation marks QUEUED -> Re-executed.
        """
        redis = Container.get("redis")
        
        logger.info("reconciler_action", job_id=job_id, action="REQUEUE", reason="lease_expired_worker_died")
        
        # 1. Update DB Status (Source of Truth) to QUEUED
        await ui_memory.update_job_status(job_id, "QUEUED", lease_owner=None, lease_expiry=None)
        
        # 2. Delete the old ephemeral Redis state to allow Idempotency SETNX again
        if redis:
            await redis.delete(f"sgr:peftlab:job:{job_id}:status")
            await redis.delete(f"sgr:peftlab:job:{job_id}:lease")
            
            # 3. Re-Enqueue into the message broker
            payload_str = job_record.get("payload")
            if payload_str:
                payload = json.loads(payload_str)
                job_payload_msg = {
                    "job_id": job_id,
                    "tenant_id": job_record.get("org_id", "default"),
                    "execution_spec": payload
                }
                await redis.rpush("sgr:peftlab:jobs", json.dumps(job_payload_msg))
                logger.info("orphaned_job_requeued", job_id=job_id)
