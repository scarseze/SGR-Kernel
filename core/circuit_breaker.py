import time
import asyncio
import structlog
from typing import Callable, Any
from functools import wraps
from core.container import Container

logger = structlog.get_logger(__name__)

class CircuitBreakerOpenException(Exception):
    """Raised when the circuit breaker is OPEN and rejecting calls."""
    pass

class DistributedCircuitBreaker:
    """
    Principal-level Shared State Circuit Breaker.
    Uses Redis to track failures across all Orchestrator instances simultaneously.
    If 10 instances hit 5 total errors, the circuit opens for all 10 instantly.
    """
    def __init__(self, service_name: str, endpoint: str = "default", failure_threshold: int = 5, recovery_timeout: int = 60):
        self.service_name = service_name
        self.endpoint = endpoint
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.count_key = f"sgr:cb:{service_name}:{endpoint}:failures"
        self.state_key = f"sgr:cb:{service_name}:{endpoint}:state"

    async def _get_redis(self):
        return Container.get("redis")

    async def record_failure(self):
        redis = await self._get_redis()
        if not redis:
            return  # Degrade gracefully if Redis is down

        now = time.time()
        
        # 1. Slide window: remove failures older than recovery_timeout
        await redis.zremrangebyscore(self.count_key, 0, now - self.recovery_timeout)
        
        # 2. Add current failure
        await redis.zadd(self.count_key, {str(now): now})
        await redis.expire(self.count_key, self.recovery_timeout)
        
        # 3. Check threshold
        fails = await redis.zcard(self.count_key)
            
        if fails >= self.failure_threshold:
            current_state = await redis.get(self.state_key)
            if current_state != b"OPEN" and current_state != "OPEN":
                logger.warning("distributed_circuit_breaker_tripped_open", service=self.service_name, endpoint=self.endpoint, fails=fails)
                # Set OPEN state with recovery timeout. After TTL, it behaves like HALF-OPEN.
                await redis.set(self.state_key, "OPEN", ex=self.recovery_timeout)

    async def record_success(self):
        redis = await self._get_redis()
        if not redis:
            return
            
        state = await redis.get(self.state_key)
        if state:
            logger.info("distributed_circuit_breaker_closed_recovery", service=self.service_name, endpoint=self.endpoint)
            await redis.delete(self.state_key)
        await redis.delete(self.count_key)

    async def allow_request(self) -> bool:
        redis = await self._get_redis()
        if not redis:
            return True # Fail-open if Redis is down
            
        state = await redis.get(self.state_key)
        if state in (b"OPEN", "OPEN"):
            return False
            
        # If the key doesn't exist, it's either CLOSED or the OPEN TTL expired (HALF-OPEN).
        # We allow the request. If it fails, `record_failure` trips it again quickly.
        return True

    def __call__(self, func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            if not await self.allow_request():
                raise CircuitBreakerOpenException(f"Distributed CB for {self.service_name} is OPEN.")
            try:
                result = await func(*args, **kwargs)
                await self.record_success()
                return result
            except CircuitBreakerOpenException:
                raise
            except Exception as e:
                await self.record_failure()
                raise e
        return async_wrapper

# Global instances of breakers for specific downstream services
rag_circuit_breaker = DistributedCircuitBreaker("cbr_rag", failure_threshold=5, recovery_timeout=60)

