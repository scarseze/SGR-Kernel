import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from core.chaos import with_chaos
from core.container import Container
from core.events import EventType, KernelEvent
from core.execution.policy import StepResult

logger = logging.getLogger(__name__)

class TaskPayload(BaseModel):
    """
    Serializable payload for a task execution request.
    """
    step_id: str
    skill_name: str
    inputs: Dict[str, Any]
    request_id: str
    attempt: int
    trace_context: Dict[str, Optional[str]]
    timeout: float = 300.0
    org_id: str = "default"

class Scheduler:
    """
    Hybrid Scheduler: Dispatches tasks either Locally or to Redis.
    """

    def __init__(self) -> None:
        self.redis = Container.get("redis")
        self.lifecycle = Container.get("lifecycle")
        # Initialize QuotaManager for org-level budgeting and rate limiting
        from core.quota import QuotaManager
        self.quota_manager = QuotaManager(self.redis)

    async def dispatch(self, tasks: List[TaskPayload]) -> List[StepResult]:
        """
        Dispatches a batch of tasks.
        Returns results (awaiting them).
        """
        if not tasks:
            return []

        # 1. Split Local vs Remote (For now, all Local if Redis missing, or specific policy)
        # Phase 5: Try Remote First if Redis is connected
        # Check if redis is enabled via Env
        import os
        use_redis = self.redis is not None and os.getenv("REDIS_HOST") not in ["mock_redis", None, ""]
        
        if use_redis:
            return await self._dispatch_distributed(tasks)  # type: ignore[no-any-return]
        else:
            return await self._dispatch_local(tasks)

    async def _dispatch_local(self, tasks: List[TaskPayload]) -> List[StepResult]:
        """
        Execute tasks in-process using asyncio.gather.
        """
        logger.info(f"⚡ Dispatching {len(tasks)} tasks LOCALLY")
        coroutines = []
        for task in tasks:
            # We already have resolved inputs in task.inputs
            # We use the new execute_task method which expects Pre-resolved inputs
            coroutines.append(self.lifecycle.execute_task(task))

        results = await asyncio.gather(*coroutines, return_exceptions=True)
        
        processed_results = []
        for res in results:
            if isinstance(res, Exception):
                logger.error(f"Local Task failed with exception: {res}", exc_info=res)
                processed_results.append(StepResult(success=False, events=[]))
            else:
                processed_results.append(res)  # type: ignore[arg-type]
        
        return processed_results

    @with_chaos
    async def _dispatch_distributed(self, tasks: List[TaskPayload]) -> List[StepResult]:
        """
        Push to Redis and Poll for results.
        """
        logger.info(f"📡 Dispatching {len(tasks)} tasks to REDIS")
        request_id = tasks[0].request_id # Assuming same request_id for batch
        
        # 1. Push all tasks
        MAX_QUEUE_SIZE = 1000
        for task in tasks:
            # Backpressure: Check global queue limit
            queue_len = await self.redis.llen("sgr:tasks")
            if queue_len >= MAX_QUEUE_SIZE:
                logger.error(f"SGR Queue Overloaded! (Limits: {MAX_QUEUE_SIZE}). Dropping Task: {task.step_id}")
                event = KernelEvent(type=EventType.STEP_FAILED, request_id=task.request_id, step_id=task.step_id, payload={"error": "429 System Overloaded (Queue Full)"})
                results_map = {t.step_id: StepResult(success=False, events=[event]) for t in tasks}
                return list(results_map.values())

            # Quota enforcement per org_id (handles noisy neighbor via rate limits)
            if not self.quota_manager.enforce(task.org_id, cost=0.0):
                logger.warning(f"Quota exceeded for org {task.org_id}. Dropping Task: {task.step_id}")
                event = KernelEvent(type=EventType.STEP_FAILED, request_id=task.request_id, step_id=task.step_id, payload={"error": "429 Quota Exceeded"})
                results_map = {t.step_id: StepResult(success=False, events=[event]) for t in tasks}
                return list(results_map.values())

            # Use global task queue, worker will handle tenant context via payload.org_id
            await self.redis.rpush("sgr:tasks", task.model_dump_json())
            
        # 2. Wait for results (Polling or Blocking Pop)
        # We need to collect N results.
        results_map = {}
        pending_ids = {t.step_id for t in tasks}
        
        # Wait loop (Timeout 600s / 10 mins) - Increased for long running skills (Training, etc)
        # FIX: Use time-based loop instead of iteration count. 
        # range(600) limits us to 600 *results*, dropping tasks if batch > 600.
        deadline = time.time() + 600
        while pending_ids and time.time() < deadline:
            if not pending_ids:
                break
                
            # Pop result for this request_id
            # List name: {org_id}:sgr:results:{request_id}
            # Using the first task's org_id
            org_id = tasks[0].org_id
            # BLPOP returns tuple (key, value) or None if timeout
            raw_res = await self.redis.blpop([f"{org_id}:sgr:results:{request_id}"], timeout=1)
            
            if raw_res:
                _, val = raw_res
                res_data = json.loads(val)
                step_id = res_data["step_id"]
                
                events_data = res_data.get("events", [])
                events_objs = [KernelEvent.model_validate(e) for e in events_data]

                # We expect dict: {success: bool, events: List[Dict]}
                step_res = StepResult(
                    success=res_data["success"],
                    events=events_objs
                )
                results_map[step_id] = step_res
                pending_ids.discard(step_id)
                
        # Return ordered results
        final_results = []
        for t in tasks:
            if t.step_id in results_map:
                final_results.append(results_map[t.step_id])
            else:
                # Timeout or Worker Crash detected - Generate explicit failure event
                logger.error(f"Task {t.step_id} timed out waiting for worker response.")
                timeout_event = KernelEvent(type=EventType.STEP_FAILED, request_id=t.request_id, step_id=t.step_id, payload={"error": "Timeout: Worker did not respond in time"})
                final_results.append(StepResult(success=False, events=[timeout_event]))
        
        return final_results

    # For compatibility during refactor, allow orchestrator to bypass logic if needed
    # (Not implemented)
