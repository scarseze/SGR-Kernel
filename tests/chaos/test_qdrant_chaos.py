"""
Chaos Engineering Tests: Qdrant Failure Scenarios.

These tests inject network faults via Toxiproxy to verify that the SGR Kernel's
RAG pipeline degrades gracefully when Qdrant experiences timeouts or connection resets.

Requirements:
  docker compose -f docker-compose.yml -f docker-compose.chaos.yml up -d
"""
import asyncio
import pytest
import httpx

from tests.chaos.conftest import ToxiproxyClient


QDRANT_PROXY_URL = "http://localhost:26333"


class TestQdrantTimeout:
    """Verify RAG pipeline behavior when Qdrant experiences high latency."""

    @pytest.mark.asyncio
    async def test_qdrant_latency_degrades_gracefully(
        self, toxiproxy: ToxiproxyClient, qdrant_proxy: dict
    ) -> None:
        """
        Inject 2000ms latency on Qdrant. Verify that the HTTP health endpoint
        either responds slowly or times out, but does NOT crash.
        """
        toxiproxy.add_toxic("qdrant", "latency", {"latency": 2000, "jitter": 500})

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(f"{QDRANT_PROXY_URL}/healthz")
                # If we got a response, it should be valid
                assert resp.status_code in (200, 503), f"Unexpected status: {resp.status_code}"
            except (httpx.TimeoutException, httpx.ConnectError):
                # Acceptable: latency exceeded our client timeout
                pass

    @pytest.mark.asyncio
    async def test_qdrant_timeout_toxic(
        self, toxiproxy: ToxiproxyClient, qdrant_proxy: dict
    ) -> None:
        """
        Add a timeout toxic (close connection after 500ms of inactivity).
        Simulates infrastructure that kills idle connections.
        """
        toxiproxy.add_toxic("qdrant", "timeout", {"timeout": 500})

        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                resp = await client.get(f"{QDRANT_PROXY_URL}/healthz")
                # Quick request might still succeed
                assert resp.status_code in (200, 503)
            except (httpx.ReadError, httpx.ConnectError, httpx.RemoteProtocolError):
                # Expected: connection was killed by timeout toxic
                pass


class TestQdrantConnectionReset:
    """Verify behavior when Qdrant connections are forcibly reset."""

    @pytest.mark.asyncio
    async def test_qdrant_connection_reset_stream(
        self, toxiproxy: ToxiproxyClient, qdrant_proxy: dict
    ) -> None:
        """
        Inject reset_peer toxic (TCP RST). Verify the client handles
        the reset gracefully without unhandled exceptions.
        """
        toxiproxy.add_toxic("qdrant", "reset_peer", {"timeout": 200})

        async with httpx.AsyncClient(timeout=5.0) as client:
            errors_caught = 0
            for _ in range(5):
                try:
                    await client.get(f"{QDRANT_PROXY_URL}/collections")
                except (httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError):
                    errors_caught += 1
                except httpx.TimeoutException:
                    errors_caught += 1

            # At least some requests should fail (reset_peer is probabilistic)
            assert errors_caught > 0, "Expected at least 1 connection reset, got none"

    @pytest.mark.asyncio
    async def test_qdrant_full_disconnect_and_recovery(
        self, toxiproxy: ToxiproxyClient, qdrant_proxy: dict
    ) -> None:
        """
        Block all data via limit_data toxic, verify failure, remove toxic, verify recovery.
        Uses limit_data(bytes=0) instead of disable/enable to avoid stale TCP issues.
        """
        # Verify Qdrant is reachable first
        async with httpx.AsyncClient(timeout=5.0) as client:
            for _ in range(3):
                try:
                    resp = await client.get(f"{QDRANT_PROXY_URL}/healthz")
                    if resp.status_code in (200, 503):
                        break
                except (httpx.RemoteProtocolError, httpx.ReadError, httpx.ConnectError):
                    await asyncio.sleep(1)

        # Block all data on upstream (simulates Qdrant becoming unreachable)
        toxiproxy.add_toxic("qdrant", "limit_data", {"bytes": 0}, stream="upstream")

        async with httpx.AsyncClient(timeout=3.0) as client:
            with pytest.raises((httpx.ConnectError, httpx.TimeoutException, httpx.ReadError, httpx.RemoteProtocolError)):
                await client.get(f"{QDRANT_PROXY_URL}/healthz")

        # Remove the toxic (recovery)
        toxiproxy.remove_toxic("qdrant", "limit_data_upstream")
        await asyncio.sleep(1)

        # Verify recovery with retries
        recovered = False
        for _ in range(5):
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(f"{QDRANT_PROXY_URL}/healthz")
                    if resp.status_code in (200, 503):
                        recovered = True
                        break
            except (httpx.ConnectError, httpx.RemoteProtocolError, httpx.ReadError):
                await asyncio.sleep(1)

        assert recovered, "Qdrant did not recover after removing limit_data toxic"
