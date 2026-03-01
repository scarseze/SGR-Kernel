import asyncio
import time
import uuid
import structlog
from typing import Optional

logger = structlog.get_logger(__name__)

class DistributedLock:
    """
    Implements a simple distributed lock (Leader Election) using Redis SETNX + PX (TTL).
    Prevents Split-Brain scenarios where multiple orchestrators run background reconciliation loops.
    """
    def __init__(self, lock_name: str, lock_timeout_ms: int = 10000):
        self.lock_name = f"sgr:lock:{lock_name}"
        self.lock_timeout_ms = lock_timeout_ms
        self.lock_value = str(uuid.uuid4())
        self.is_leader = False
        self._renew_task: Optional[asyncio.Task] = None

    async def acquire_and_hold(self):
        """
        Attempts to acquire the lock. If successful, spawns a background task to renew it.
        Returns True if leadership is acquired.
        """
        from core.container import Container
        redis = Container.get("redis")
        if not redis:
            return False

        # nx=True: set only if not exists. px=lock_timeout_ms: expiration time
        acquired = await redis.set(self.lock_name, self.lock_value, nx=True, px=self.lock_timeout_ms)
        
        if acquired:
            self.is_leader = True
            logger.info("leader_election_won", lock_name=self.lock_name, member_id=self.lock_value)
            if self._renew_task is None or self._renew_task.done():
                self._renew_task = asyncio.create_task(self._renew_loop())
            return True
            
        return False

    async def _renew_loop(self):
        """Background task that periodically extends the lock TTL while holding leadership."""
        from core.container import Container
        redis = Container.get("redis")
        
        # Determine strict renewal interval (half the timeout is standard)
        renew_interval = (self.lock_timeout_ms / 1000.0) / 2.0
        
        while self.is_leader:
            await asyncio.sleep(renew_interval)
            
            if not redis:
                break
                
            # Lua script to safely renew the lock ONLY if we still hold it
            # This prevents extending a lock that was lost due to a long GC pause
            script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("pexpire", KEYS[1], ARGV[2])
            else
                return 0
            end
            """
            try:
                result = await redis.eval(script, 1, self.lock_name, self.lock_value, self.lock_timeout_ms)
                if not result:
                    logger.warning("leader_lock_lost_during_renewal", lock_name=self.lock_name)
                    self.is_leader = False
                    break
            except Exception as e:
                logger.error("leader_lock_renewal_error", error=str(e))
                # Do not immediately renounce leadership on a transient error, but next cycle might fail

    async def release(self):
        """Releases the lock gracefully if we hold it."""
        self.is_leader = False
        if self._renew_task:
            self._renew_task.cancel()
            self._renew_task = None
            
        from core.container import Container
        redis = Container.get("redis")
        if redis:
            # Safe release script: only delete if the value matches us
            script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
            """
            try:
                await redis.eval(script, 1, self.lock_name, self.lock_value)
                logger.info("leader_lock_released", lock_name=self.lock_name)
            except Exception:
                pass
