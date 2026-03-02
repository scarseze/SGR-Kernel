import asyncio
import logging
import os
import random
import time
from functools import wraps
from typing import Callable

logger = logging.getLogger("core.chaos")

class ChaosException(Exception):
    """Exception raised by ChaosMonkey to simulate failures."""
    def __init__(self, message="Simulated Chaos Failure"):
        super().__init__(message)

def is_chaos_enabled() -> bool:
    return os.environ.get("ENABLE_CHAOS", "false").lower() == "true"

def get_chaos_rate() -> float:
    try:
        return float(os.environ.get("CHAOS_FAILURE_RATE", "0.0"))
    except ValueError:
        return 0.0

def get_chaos_max_delay() -> float:
    try:
        return float(os.environ.get("CHAOS_MAX_DELAY", "2.0"))
    except ValueError:
        return 2.0

def get_chaos_min_delay() -> float:
    try:
        return float(os.environ.get("CHAOS_MIN_DELAY", "0.0"))
    except ValueError:
        return 0.0

def with_chaos(func: Callable) -> Callable:
    """
    Decorator that injects Random Latency and Failures if Chaos mode is enabled.
    Supports both synchronous and asynchronous functions.
    """
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        if is_chaos_enabled():
            # 1. Inject Latency
            delay = random.uniform(get_chaos_min_delay(), get_chaos_max_delay())
            if delay > 0.5:
                logger.warning(f"🐒 [CHAOS] Injecting latency: {delay:.2f}s before {func.__name__}")
            await asyncio.sleep(delay)
            
            # 2. Inject Failure
            if random.random() < get_chaos_rate():
                logger.error(f"🐒 [CHAOS] Injecting simulated failure in {func.__name__}")
                raise ChaosException(f"ChaosMonkey simulated failure in {func.__name__}")
                
        return await func(*args, **kwargs)

    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        if is_chaos_enabled():
            # 1. Inject Latency
            delay = random.uniform(get_chaos_min_delay(), get_chaos_max_delay())
            if delay > 0.5:
                logger.warning(f"🐒 [CHAOS] Injecting latency: {delay:.2f}s before {func.__name__}")
            time.sleep(delay)
            
            # 2. Inject Failure
            if random.random() < get_chaos_rate():
                logger.error(f"🐒 [CHAOS] Injecting simulated failure in {func.__name__}")
                raise ChaosException(f"ChaosMonkey simulated failure in {func.__name__}")
                
        return func(*args, **kwargs)

    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper

# --- Specific Triggers for Manual Chaos Testing ---

def inject_redis_failure(redis_client):
    """Mocks redis client to raise ChaosException on next call."""
    if not is_chaos_enabled():
        return
    
    original_get = redis_client.get
    async def broken_get(*args, **kwargs):
        logger.error("🐒 [CHAOS] Redis failure injected!")
        raise ChaosException("Simulated Redis Connection Error")
        
    redis_client.get = broken_get
    return original_get

def inject_docker_hang():
    """Sets env to trigger long delays in DockerMCPClient (if it uses with_chaos)."""
    os.environ["ENABLE_CHAOS"] = "true"
    os.environ["CHAOS_MAX_DELAY"] = "10.0"
    os.environ["CHAOS_FAILURE_RATE"] = "1.0"
    logger.warning("🐒 [CHAOS] Docker Hang/Failure mode enabled.")

def inject_network_partition(httpx_client=None):
    """Simulates a network partition by dropping all external bounds via httpx/requests."""
    logger.error("🐒 [CHAOS] Network Partition Injected! All outbound connections will fail.")
    if httpx_client:
        async def broken_send(*args, **kwargs):
            raise ChaosException("503 Service Unavailable: Network Partition Simulated")
        httpx_client.send = broken_send

def inject_p99_latency():
    """Forces all chaos wrappers to hit maximum delay simulating p99 tail latency spikes."""
    os.environ["ENABLE_CHAOS"] = "true"
    os.environ["CHAOS_MIN_DELAY"] = "3.0"  # Force lower bound
    os.environ["CHAOS_MAX_DELAY"] = "5.0"
    logger.warning("🐒 [CHAOS] P99 Latency Spike simulated (3-5s artificial delay).")
