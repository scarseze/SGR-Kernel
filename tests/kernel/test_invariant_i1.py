import asyncio
import uuid
import pytest
from hypothesis import given, settings, strategies as st
from datetime import datetime, timezone, timedelta
from core.ui_memory import UIMemory

@pytest.mark.asyncio
@given(
    worker_delays=st.lists(st.floats(min_value=0.0, max_value=0.05), min_size=2, max_size=10)
)
@settings(max_examples=50, deadline=None)
async def test_execution_exclusivity(worker_delays):
    """
    TLA+ Invariant I1: Execution Exclusivity
    Proves that CAS strictly prevents multiple workers from acquiring the same lease concurrently.
    """
    mem = UIMemory("sqlite+aiosqlite:///:memory:")
    await mem.initialize()
    
    job_id = str(uuid.uuid4())
    await mem.create_job(job_id, "org-1", {"task": "test"})
    
    # Initial status
    await mem.update_job_status(job_id, "QUEUED")
    
    expected_version = 0
    
    async def worker_attempt(delay: float, worker_id: int):
        await asyncio.sleep(delay)
        expiry = datetime.now(timezone.utc) + timedelta(minutes=5)
        # Attempt to acquire the lease using CAS
        success = await mem.update_job_status(
            job_id, 
            "RUNNING", 
            lease_owner=f"worker-{worker_id}", 
            lease_expiry=expiry, 
            expected_version=expected_version
        )
        return success

    # Run all workers concurrently
    tasks = [worker_attempt(delay, i) for i, delay in enumerate(worker_delays)]
    results = await asyncio.gather(*tasks)
    
    # INVARIANT I1: Exactly ONE worker should succeed in acquiring the lease.
    # The others must fail the CAS check because expected_version will have incremented.
    successful_acquisitions = sum(1 for r in results if r is True)
    assert successful_acquisitions == 1, f"Execution Exclusivity violated! Successful acquires: {successful_acquisitions}"
