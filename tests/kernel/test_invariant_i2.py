import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import select

from core.container import Container
from core.reconciler import BackgroundReconciler
from core.ui_memory import UIMemory


@pytest.mark.asyncio
@given(
    crash_indices=st.lists(st.integers(min_value=0, max_value=9), max_size=10, unique=True)
)
@settings(max_examples=50, deadline=None)
async def test_at_least_once_delivery(crash_indices):
    """
    TLA+ Invariant I2: At-Least-Once Delivery
    Proves that a Reconciler guarantees progress even if workers crash arbitrarily.
    """
    mem = UIMemory("sqlite+aiosqlite:///:memory:")
    await mem.initialize()
    
    mock_redis = AsyncMock()
    # Fix the generic AsyncMock by mocking redis_pool
    class MockRedisPool:
        async def release(self, *args): pass
    
    mock_redis.pipeline.return_value = AsyncMock()
    mock_redis.connection_pool = MockRedisPool()

    Container.register("ui_memory", mem)
    Container.register("redis", mock_redis)
    reconciler = BackgroundReconciler(scan_interval_seconds=0)
    
    jobs = []
    
    for _ in range(10):
        job_id = f"job-{uuid.uuid4()}"
        await mem.create_job(job_id, "org-1", {"task": "test"})
        jobs.append(job_id)
        
    for i, job_id in enumerate(jobs):
        if i in crash_indices:
            # Simulate a worker pulling the job and crashing immediately.
            # The lease expires in the past.
            expiry = datetime.now(timezone.utc) - timedelta(minutes=5)
            await mem.update_job_status(job_id, "RUNNING", lease_expiry=expiry, expected_version=0)
        else:
            # Worker successfully completed it
            await mem.update_job_status(job_id, "COMPLETED", expected_version=0)
            
    # Run the background reconciler loop once
    await reconciler._sweep_orphaned_jobs()

    # Verify I2
    async with mem.engine.connect() as conn:
        for i, job_id in enumerate(jobs):
            result = await conn.execute(select(mem.jobs.c.status).where(mem.jobs.c.job_id == job_id))
            status = result.scalar()
            
            if i in crash_indices:
                # Must be recovered back to QUEUED
                assert status == "QUEUED", f"Job {job_id} was lost! Status: {status}"
            else:
                assert status == "COMPLETED", f"Job {job_id} should be COMPLETED! Status: {status}"
