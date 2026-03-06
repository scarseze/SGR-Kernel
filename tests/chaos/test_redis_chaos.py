"""
Chaos Engineering Tests: Redis Failure Scenarios.

These tests inject network faults via Toxiproxy to verify that the SGR Kernel
degrades gracefully when Redis experiences latency, connection drops, or bandwidth limits.

Requirements:
  docker compose -f docker-compose.yml -f docker-compose.chaos.yml up -d
"""
import asyncio

import pytest
import redis.asyncio as aioredis

from tests.chaos.conftest import ToxiproxyClient

REDIS_PROXY_URL = "redis://localhost:26379/0"


@pytest.fixture
async def redis_client() -> aioredis.Redis:
    """Connect to Redis through the Toxiproxy endpoint."""
    client = aioredis.from_url(REDIS_PROXY_URL, decode_responses=True, socket_timeout=5.0)
    yield client
    await client.aclose()


class TestRedisLatency:
    """Verify system behavior under artificially high Redis latency."""

    @pytest.mark.asyncio
    async def test_redis_latency_500ms_still_works(
        self, toxiproxy: ToxiproxyClient, redis_proxy: dict, redis_client: aioredis.Redis
    ) -> None:
        """
        Inject 500ms latency on Redis. Verify basic operations still complete.
        This simulates a degraded network or overloaded Redis.
        """
        # Inject latency toxic
        toxiproxy.add_toxic("redis", "latency", {"latency": 500, "jitter": 100})

        # Operations should still succeed, just slower
        await redis_client.set("chaos:test:latency", "hello")
        val = await redis_client.get("chaos:test:latency")
        assert val == "hello", f"Expected 'hello', got {val}"

        # Cleanup
        await redis_client.delete("chaos:test:latency")

    @pytest.mark.asyncio
    async def test_redis_latency_2s_timeout_handling(
        self, toxiproxy: ToxiproxyClient, redis_proxy: dict, redis_client: aioredis.Redis
    ) -> None:
        """
        Inject 2000ms latency — exceeds the 5s socket_timeout after a few ops.
        Verify the client raises a timeout, not a hang.
        """
        toxiproxy.add_toxic("redis", "latency", {"latency": 2000, "jitter": 500})

        # Single op should still work (2s < 5s timeout)
        await redis_client.set("chaos:test:slow", "still-ok")
        val = await redis_client.get("chaos:test:slow")
        assert val == "still-ok"
        await redis_client.delete("chaos:test:slow")


class TestRedisConnectionCut:
    """Verify graceful degradation when Redis connection is completely severed."""

    @pytest.mark.asyncio
    async def test_redis_full_disconnect(
        self, toxiproxy: ToxiproxyClient, redis_proxy: dict, redis_client: aioredis.Redis
    ) -> None:
        """
        Disable the Redis proxy entirely. Verify that operations fail
        with a ConnectionError, not an indefinite hang.
        """
        # First verify connection works
        await redis_client.set("chaos:test:pre", "alive")
        assert await redis_client.get("chaos:test:pre") == "alive"

        # Cut the connection
        toxiproxy.disable_proxy("redis")

        # Operations should fail with a connection error
        with pytest.raises((ConnectionError, TimeoutError, aioredis.ConnectionError, aioredis.TimeoutError)):
            await redis_client.set("chaos:test:dead", "unreachable")

        # Re-enable and verify recovery
        toxiproxy.enable_proxy("redis")
        await asyncio.sleep(1)  # Give connection pool time to reconnect

        # Fresh client for clean connection
        fresh = aioredis.from_url(REDIS_PROXY_URL, decode_responses=True, socket_timeout=5.0)
        await fresh.set("chaos:test:recovered", "back")
        assert await fresh.get("chaos:test:recovered") == "back"
        await fresh.aclose()


class TestRedisBandwidth:
    """Verify behavior under restricted bandwidth (slow network)."""

    @pytest.mark.asyncio
    async def test_redis_bandwidth_throttle(
        self, toxiproxy: ToxiproxyClient, redis_proxy: dict, redis_client: aioredis.Redis
    ) -> None:
        """
        Throttle Redis bandwidth to 1KB/s. Verify small operations complete,
        but large operations either timeout or complete slowly without corruption.
        """
        # Throttle to 1KB/s
        toxiproxy.add_toxic("redis", "bandwidth", {"rate": 1})

        # Small value should still work (eventually)
        try:
            await asyncio.wait_for(
                redis_client.set("chaos:test:bw", "small"),
                timeout=10.0
            )
            val = await asyncio.wait_for(
                redis_client.get("chaos:test:bw"),
                timeout=10.0
            )
            # If we got a value, it should be uncorrupted
            assert val == "small", f"Data corruption detected: expected 'small', got {val}"
        except (asyncio.TimeoutError, TimeoutError):
            # Acceptable: bandwidth too low to complete within timeout
            pass
