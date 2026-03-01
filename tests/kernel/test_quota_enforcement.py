import pytest
import asyncio
import os
from unittest.mock import MagicMock, patch, AsyncMock
from core.scheduler import Scheduler, TaskPayload
from core.quota import QuotaManager
from core.execution.policy import StepResult

@pytest.mark.asyncio
async def test_quota_enforcement_triggers_429():
    """Verify that Scheduler returns 429 when QuotaManager blocks request."""
    mock_redis = MagicMock()
    mock_redis.llen = AsyncMock(return_value=0)
    mock_redis.rpush = AsyncMock()
    mock_redis.get = AsyncMock(return_value="0.0") # Empty budget
    mock_redis.setnx = MagicMock(return_value=True)
    mock_redis.expire = MagicMock(return_value=True)
    mock_redis.eval = MagicMock(return_value=1001)
    
    mock_lifecycle = MagicMock()
    mock_lifecycle.execute_task = AsyncMock()

    def mock_get(k):
        if k == "redis": return mock_redis
        if k == "lifecycle": return mock_lifecycle
        return MagicMock()
        
    with patch.dict(os.environ, {"REDIS_HOST": "localhost", "ENABLE_CHAOS": "false"}), \
         patch("core.container.Container.get", side_effect=mock_get):
        scheduler = Scheduler()
        # Ensure QuotaManager is initialized with the mock redis
        scheduler.quota_manager.redis = mock_redis
        
        payload = TaskPayload(
            step_id="s1", 
            skill_name="test", 
            inputs={}, 
            request_id="req1", 
            org_id="poor_org", 
            attempt=1, 
            trace_context={}
        )
        
        # Result should be a 429 StepResult
        results = await scheduler.dispatch([payload])
        assert len(results) == 1
        assert results[0].success is False
        assert "429 Quota Exceeded" in results[0].events[0].payload["error"]

@pytest.mark.asyncio
async def test_backpressure_triggers_429():
    """Verify that Scheduler returns 429 when Redis queue is full."""
    mock_redis = MagicMock()
    # Simulate full queue
    mock_redis.llen = AsyncMock(return_value=10000)
    mock_redis.rpush = AsyncMock() 
    mock_redis.get = AsyncMock(return_value="100.0")
    mock_redis.eval = MagicMock(return_value=1)
    
    mock_lifecycle = MagicMock()
    mock_lifecycle.execute_task = AsyncMock()

    def mock_get(k):
        if k == "redis": return mock_redis
        if k == "lifecycle": return mock_lifecycle
        return MagicMock()

    with patch.dict(os.environ, {"REDIS_HOST": "localhost", "ENABLE_CHAOS": "false"}), \
         patch("core.container.Container.get", side_effect=mock_get):
        scheduler = Scheduler()
        scheduler.quota_manager.redis = mock_redis
        
        payload = TaskPayload(
            step_id="s1", 
            skill_name="test", 
            inputs={}, 
            request_id="req1", 
            org_id="rich_org", 
            attempt=1, 
            trace_context={}
        )
        
        results = await scheduler.dispatch([payload])
        assert len(results) == 1
        assert results[0].success is False
        assert "429 System Overloaded" in results[0].events[0].payload["error"]
