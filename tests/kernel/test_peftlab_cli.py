import pytest
import json
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from skills.peftlab.handler import PEFTLabSkill
from skills.peftlab.schema import PEFTlabRequest

@pytest.fixture
def skill():
    return PEFTLabSkill()

@pytest.mark.asyncio
async def test_peftlab_generate_config(skill):
    req = PEFTlabRequest(
        action="analyze_sensitivity",
        dataset_path="data/train.jsonl",
        base_model="meta-llama/Llama-2-7b-hf"
    )

    config = skill._generate_config(req)
        
    # Verify standard dict contents
    assert config["experiment"]["action"] == "analyze_sensitivity"
    assert config["experiment"]["dataset"]["path"] == "data/train.jsonl"
    assert config["experiment"]["model"]["base_name"] == "meta-llama/Llama-2-7b-hf"
    assert config["experiment"]["sensitivity"]["max_samples"] == 8

def _make_drf_aware_redis_mock(lpop_return_value=None):
    """Creates a mock Redis client that supports DRF multi-dimensional quota operations."""
    mock_redis = AsyncMock()
    
    # DRF Admission Control support
    mock_redis.hgetall.return_value = {}  # Empty usage — tenant is fresh
    mock_redis.get.return_value = None    # Circuit breaker not open
    
    # Pipeline mock for DRF reservation and cleanup
    # redis.pipeline() is a SYNC call. Since mock_redis is AsyncMock,
    # we must explicitly override pipeline to be a regular MagicMock.
    mock_pipe = MagicMock()
    mock_pipe.hincrby = MagicMock(return_value=mock_pipe)  # chainable
    mock_pipe.expire = MagicMock(return_value=mock_pipe)   # chainable
    mock_pipe.execute = AsyncMock(return_value=[])
    mock_redis.pipeline = MagicMock(return_value=mock_pipe)
    
    # Core job flow
    mock_redis.rpush = AsyncMock()
    mock_redis.lpop.return_value = lpop_return_value
    
    # UI Memory mock
    mock_ui_memory = MagicMock()
    mock_ui_memory.create_job.return_value = True
    mock_ui_memory.update_job_status.return_value = True
    
    return mock_redis, mock_ui_memory

@pytest.mark.asyncio
@patch("skills.peftlab.handler.Container")
async def test_peftlab_push_to_execution_plane(mock_container, skill):
    """Verify that jobs are correctly published to the REDIS queue with trace IDs."""
    req = PEFTlabRequest(
        action="tune_hyperparameters",
        dataset_path="data/train.jsonl",
        base_model="meta-llama/Llama-2-7b-hf"
    )
    
    result_payload = json.dumps({
        "status": "success",
        "mock_s3_uri": "s3://sgr-artifacts-bucket/tenant-xyz/peftlab/test/_SUCCESS",
        "artifacts": {
            "best_hyperparameters": {"lora_r": 32, "lora_alpha": 64, "learning_rate": 1e-4},
            "best_value": 0.99
        }
    }).encode("utf-8")
    
    mock_redis, mock_ui_memory = _make_drf_aware_redis_mock(lpop_return_value=result_payload)
    
    def container_get(key):
        if key == "redis":
            return mock_redis
        if key == "ui_memory":
            return mock_ui_memory
        return MagicMock()
    
    mock_container.get.side_effect = container_get
    
    state = {"org_id": "tenant-xyz", "trace_id": "trace-123"}
    
    # Execute
    res = await skill.execute(req, state)
    
    # Assert
    # 1. Did it push to queue?
    mock_redis.rpush.assert_called_once()
    queue_name, payload_str = mock_redis.rpush.call_args[0]
    assert queue_name == "sgr:peftlab:jobs"
    
    payload = json.loads(payload_str)
    assert payload["tenant_id"] == "tenant-xyz"
    assert "job_id" in payload
    # V2 uses execution_spec instead of flat config/trace_id
    assert "execution_spec" in payload
    
    # 2. Did it try to pop the results?
    mock_redis.lpop.assert_called_once()
    lpop_queue = mock_redis.lpop.call_args[0][0]
    assert lpop_queue == f"sgr:peftlab:results:{payload['job_id']}"
    
    # 3. Proper formatting?
    assert "Optimal Hyperparameters Discovered" in res
    assert "`32`" in res

@pytest.mark.asyncio
@patch("skills.peftlab.handler.Container")
async def test_peftlab_worker_timeout(mock_container, skill):
    req = PEFTlabRequest(action="train_final_model", dataset_path="test", base_model="test", hyperparams={})
    
    mock_redis, mock_ui_memory = _make_drf_aware_redis_mock(lpop_return_value=None)
    
    def container_get(key):
        if key == "redis":
            return mock_redis
        if key == "ui_memory":
            return mock_ui_memory
        return MagicMock()
    
    mock_container.get.side_effect = container_get
    
    # To avoid the test hanging for 1 hour, patch asyncio.sleep to do nothing and proceed loop instantly
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        res = await skill.execute(req)
        
        # We expect 360 polls attempts
        assert mock_redis.lpop.call_count == 360
        assert mock_sleep.call_count == 360
        
        # Verify fallback error message
        assert "timed out waiting for Execution Plane workers" in res
