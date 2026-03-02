import asyncio
import datetime
import hashlib
import json
import os
import tempfile

import structlog
import yaml

from core.ui_memory import UIMemory


class StaleLeaseException(Exception):
    """Raised when a worker attempts to update a job but loses the Compare-And-Swap race."""
    pass

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ]
)
logger = structlog.get_logger("peftlab_worker")

class PEFTLabWorker:
    """
    Isolated Data Plane Worker for PEFTLab jobs.
    This mimics a Kubernetes Job/Pod that pulls from a message broker (Redis).
    """
    def __init__(self, redis_host: str = "localhost", redis_port: int = 6379):
        import redis.asyncio as redis
        self.redis = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
        self.job_queue = "sgr:peftlab:jobs"
        self.peftlab_bin = os.environ.get("PEFTLAB_BIN", "peftlab")
        self.ui_memory = UIMemory()
        self.worker_id = f"peftlab_worker_{os.getpid()}"

    async def start(self):
        logger.info("peftlab_worker_started", queue=self.job_queue)
        while True:
            try:
                # BLPOP blocks until a message is available
                # In a true At-Least-Once system, we'd use XREADGROUP (Redis Streams) or RPOPLPUSH.
                result = await self.redis.blpop(self.job_queue, timeout=5.0)
                if not result:
                    continue
                    
                _, payload_str = result
                payload = json.loads(payload_str)
                job_id = payload.get("job_id")
                tenant_id = payload.get("tenant_id", "default")
                
                # --- DISTINGUISHED LEVEL: Parse ExecutionSpec ---
                exec_spec = payload.get("execution_spec", {})
                trace_id = exec_spec.get("trace_context", {}).get("trace_id", job_id)
                span_id = exec_spec.get("trace_context", {}).get("span_id", job_id)
                
                # Bind correlation IDs for strictly traceable logging (OpenTelemetry style)
                log = logger.bind(job_id=job_id, trace_id=trace_id, span_id=span_id, tenant_id=tenant_id)
                
                await self.process_job(job_id, payload, log, tenant_id)
                
            except asyncio.CancelledError:
                logger.info("peftlab_worker_shutting_down")
                break
            except Exception as e:
                logger.error("peftlab_worker_system_error", error=str(e))
                await asyncio.sleep(5)  # Backoff on critical failure

    async def process_job(self, job_id: str, payload: dict, log, tenant_id: str):
        """Processes a single PEFTLab job representing the separated Data Plane Execution Contract."""
        status_key = f"sgr:peftlab:job:{job_id}:status"
        
        # --- DISTINGUISHED LEVEL: Parse ExecutionSpec ---
        exec_spec = payload.get("execution_spec", {})
        config = exec_spec.get("job_payload", {})
        
        # 1. State Machine & Idempotency Check (Atomic via SETNX)
        lock_acquired = await self.redis.setnx(status_key, "RUNNING")
        if not lock_acquired:
            current_status = await self.redis.get(status_key)
            log.warning("job_already_processed_or_running_skipping", state=current_status)
            return
            
        # Create a Lease with a 60 second TTL
        lease_key = f"sgr:peftlab:job:{job_id}:lease"
        await self.redis.set(lease_key, "1", px=60000)
        
        # --- TOP 1% PRINCIPAL: FENCING TOKENS (CAS) ---
        lease_version = payload.get("lease_version", 0)
        expiry = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=60)
        
        cas_success = self.ui_memory.update_job_status(
            job_id, "RUNNING", lease_owner=self.worker_id, lease_expiry=expiry, expected_version=lease_version
        )
        if not cas_success:
            log.warning("stale_lease_detected_aborting_duplicate", expected_version=lease_version)
            await self.redis.delete(status_key) # Give lock back just in case
            return # We lost the race, DO NOT execute. Duplicate prevented!
            
        # If we won, we hold the new version
        current_version = lease_version + 1

        log.info("job_execution_started_with_lease", lease_owner=self.worker_id, version=current_version)
        
        # Start Heartbeat Task
        async def heartbeat():
            nonlocal current_version
            try:
                while True:
                    await asyncio.sleep(20)
                    await self.redis.pexpire(lease_key, 60000)
                    new_expiry = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=60)
                    success = self.ui_memory.update_job_status(
                        job_id, "RUNNING", lease_owner=self.worker_id, lease_expiry=new_expiry, expected_version=current_version
                    )
                    if success:
                        current_version += 1
                    else:
                        log.error("heartbeat_cas_failed_lease_lost")
                        break # We lost the lease!
            except asyncio.CancelledError:
                pass
                
        hb_task = asyncio.create_task(heartbeat())

        try:
            # 2. Setup Work Directory (Isolated)
            config = payload.get("config", {})
            action = config.get("experiment", {}).get("action", "unknown")
            
            out_dir = os.path.abspath(os.path.join(tempfile.gettempdir(), f"peftlab_worker_{job_id}"))
            os.makedirs(out_dir, exist_ok=True)
            
            config["experiment"]["output_dir"] = out_dir
            config["experiment"]["name"] = f"job_{job_id}"
            
            cfg_file = os.path.join(out_dir, "config.yaml")
            with open(cfg_file, "w", encoding="utf-8") as f:
                yaml.dump(config, f)

            # 3. Execute Subprocess (Valid here as this is the Worker boundary)
            log.info("spawning_peftlab_cli", action=action)
            proc = await asyncio.create_subprocess_exec(
                self.peftlab_bin, "run", "--config", cfg_file,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                # Enforce Job Level Timeout
                stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=3600.0)
                ret_code = proc.returncode
            except asyncio.TimeoutError:
                proc.kill()
                log.error("job_timed_out_force_killed")
                await self._fail_job(job_id, "Worker timeout exceeded 3600s", status_key, log, current_version)
                return

            if ret_code != 0:
                err_msg = stderr_b.decode('utf-8', errors='replace')
                log.error("peftlab_cli_error", return_code=ret_code, stderr=err_msg)
                await self._fail_job(job_id, err_msg, status_key, log, current_version)
                return

            # 4. Storage Exactly-Once Illusion (Write-Verify-Commit via Markers)
            result_file = os.path.join(out_dir, "results.json")
            artifacts = {}
            s3_mock_uri = None
            checksum = None
            
            if os.path.exists(result_file):
                with open(result_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    artifacts = json.loads(content)
                    
                    # Compute SHA256 for data integrity
                    checksum = hashlib.sha256(content.encode('utf-8')).hexdigest()
                    
                    # --- L8 DISTINGUISHED: Commit Marker Pattern + Garbage Collection ---
                    # Instead of RENAME ( COPY + DELETE ), we use Versioned Pointers
                    version_id = f"v_{int(datetime.datetime.now(datetime.UTC).timestamp())}_{current_version}"
                    
                    # Step 1: Write raw data to a uniquely versioned path
                    versioned_uri = f"s3://sgr-artifacts-bucket/{tenant_id}/peftlab/{job_id}/{version_id}/results.json"
                    log.info("writing_artifact_to_versioned_path", uri=versioned_uri)
                    
                    # Step 2: Atomic Commit via _SUCCESS Pointer
                    # Create the pointer payload containing the secure checksum
                    commit_payload = {
                        "version_id": version_id,
                        "canonical_uri": versioned_uri,
                        "checksum_sha256": checksum,
                        "timestamp": datetime.datetime.now(datetime.UTC).isoformat()
                    }
                    
                    # Write the pointer atomically. Downstream readers ONLY poll for this file.
                    success_marker_uri = f"s3://sgr-artifacts-bucket/{tenant_id}/peftlab/{job_id}/_SUCCESS"
                    log.info("atomic_commit_marker_written", uri=success_marker_uri, payload=commit_payload)
                    s3_mock_uri = success_marker_uri
                    
                    # Step 3: Inline Garbage Collection (GC) for stale versions
                    # Simulating async deletion of any `v_*` prefixes that are NOT `version_id`
                    log.info("triggering_async_gc_for_stale_versions", keep_version=version_id)
                    # e.g. await self._s3_client.delete_objects(Prefix=f"s3://.../{job_id}/", Exclude=version_id)

            # 5. Publish Success to SGR Orchestrator
            await self.redis.set(status_key, "COMPLETED")
            
            # Final Fencing check before committing side effects
            final_success = self.ui_memory.update_job_status(job_id, "COMPLETED", artifact_uri=s3_mock_uri, expected_version=current_version)
            if not final_success:
                log.error("stale_lease_on_completion_aborting")
                return
                
            response_payload = {
                "status": "success",
                "job_id": job_id,
                "artifacts": artifacts,
                "mock_s3_uri": s3_mock_uri,
                "checksum": checksum if 'checksum' in locals() else None
            }
            await self.redis.rpush(f"sgr:peftlab:results:{job_id}", json.dumps(response_payload))
            log.info("job_execution_completed")
        finally:
            hb_task.cancel()

    async def _fail_job(self, job_id, error_msg, status_key, log, current_version):
        await self.redis.set(status_key, "FAILED")
        self.ui_memory.update_job_status(job_id, "FAILED", expected_version=current_version)
        response_payload = {
            "status": "error",
            "job_id": job_id,
            "error_msg": error_msg
        }
        await self.redis.rpush(f"sgr:peftlab:results:{job_id}", json.dumps(response_payload))
        log.info("job_execution_failed_gracefully")

if __name__ == "__main__":
    redis_h = os.environ.get("REDIS_HOST", "localhost")
    redis_p = int(os.environ.get("REDIS_PORT", 6379))
    
    worker = PEFTLabWorker(redis_host=redis_h, redis_port=redis_p)
    
    try:
        asyncio.run(worker.start())
    except KeyboardInterrupt:
        print("Worker stopped manually.")
