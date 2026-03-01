import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class QuotaManager:
    """Simple org‑level quota manager backed by Redis.
    Stores two keys per org:
        {org_id}:budget   – remaining USD budget (float)
        {org_id}:rate     – number of requests in current window (int)
    The window is a simple sliding counter that resets every minute.
    """

    def __init__(self, redis_client, default_budget: float = 10.0, rate_limit: int = 1000, window_seconds: int = 60):
        self.redis = redis_client
        self.default_budget = default_budget
        self.rate_limit = rate_limit
        self.window_seconds = window_seconds

    def _budget_key(self, org_id: str) -> str:
        return f"{org_id}:budget"

    def _rate_key(self, org_id: str) -> str:
        return f"{org_id}:rate"

    def init_org(self, org_id: str):
        """Create budget and rate keys for a new org if they do not exist."""
        budget_key = self._budget_key(org_id)
        rate_key = self._rate_key(org_id)
        # Use SETNX to avoid overwriting existing values
        self.redis.setnx(budget_key, self.default_budget)
        self.redis.setnx(rate_key, 0)
        # Set expiry for rate counter (window)
        self.redis.expire(rate_key, self.window_seconds)
        logger.debug(f"QuotaManager: initialized org {org_id} with budget {self.default_budget} and rate limit {self.rate_limit}")

    def get_budget(self, org_id: str) -> float:
        val = self.redis.get(self._budget_key(org_id))
        if val is None:
            self.init_org(org_id)
            val = self.redis.get(self._budget_key(org_id))
        try:
            return float(val)
        except (ValueError, TypeError):
            return 0.0

    def deduct(self, org_id: str, amount: float) -> bool:
        """Atomically deduct amount from budget using a Lua script."""
        budget_key = self._budget_key(org_id)
        
        # Ensure org initialized
        if self.redis.get(budget_key) is None:
            self.init_org(org_id)
            
        script = """
        local current = tonumber(redis.call('get', KEYS[1]))
        local amount = tonumber(ARGV[1])
        if current == nil then
            return 0
        end
        if current < amount then
            return 0
        end
        redis.call('set', KEYS[1], current - amount)
        return 1
        """
        result = self.redis.eval(script, 1, budget_key, amount)
        if result == 1:
            logger.debug(f"QuotaManager: deducted ${amount:.2f} from org {org_id}")
            return True
        return False

    def check_rate(self, org_id: str) -> bool:
        """Atomically increment and check rate using a Lua script."""
        rate_key = self._rate_key(org_id)
        script = """
        local current = redis.call('incr', KEYS[1])
        if tonumber(current) == 1 then
            redis.call('expire', KEYS[1], ARGV[1])
        end
        return current
        """
        current = self.redis.eval(script, 1, rate_key, self.window_seconds)
        if current > self.rate_limit:
            logger.warning(f"QuotaManager: rate limit exceeded for org {org_id} ({current}/{self.rate_limit})")
            return False
        return True

    def enforce(self, org_id: str, cost: float) -> bool:
        """Check both rate and budget. Returns True if request may proceed, False otherwise."""
        if not self.check_rate(org_id):
            return False
        if cost > 0:
            if not self.deduct(org_id, cost):
                logger.warning(f"QuotaManager: budget exhausted for org {org_id}")
                return False
        return True
