"""
Chaos Engineering Test Suite — Toxiproxy Fixtures.

Usage:
  docker compose -f docker-compose.yml -f docker-compose.chaos.yml up -d
  pytest tests/chaos/ -v

Tests are automatically SKIPPED if Toxiproxy is not reachable (local dev without Docker).
"""
import os
import pytest
import httpx
from typing import Any, Dict, Generator

TOXIPROXY_API = os.getenv("TOXIPROXY_API", "http://localhost:8474")

# ---------- Skip Guard ----------

def _toxiproxy_reachable() -> bool:
    """Check if the Toxiproxy API is reachable."""
    try:
        r = httpx.get(f"{TOXIPROXY_API}/version", timeout=2.0)
        return r.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException):
        return False

pytestmark = pytest.mark.skipif(
    not _toxiproxy_reachable(),
    reason="Toxiproxy not reachable (run docker compose -f docker-compose.yml -f docker-compose.chaos.yml up -d)"
)

# ---------- Toxiproxy Client ----------

class ToxiproxyClient:
    """Minimal Toxiproxy REST API client for test fixtures."""

    def __init__(self, api_url: str = TOXIPROXY_API) -> None:
        self.api_url = api_url
        self.client = httpx.Client(base_url=api_url, timeout=5.0)

    def create_proxy(self, name: str, listen: str, upstream: str) -> Dict[str, Any]:
        """Create or reset a proxy."""
        # Delete if exists
        try:
            self.client.delete(f"/proxies/{name}")
        except httpx.HTTPStatusError:
            pass
        resp = self.client.post("/proxies", json={
            "name": name,
            "listen": listen,
            "upstream": upstream,
            "enabled": True
        })
        resp.raise_for_status()
        return resp.json()

    def add_toxic(self, proxy_name: str, toxic_type: str, attributes: Dict[str, Any],
                  stream: str = "downstream", toxicity: float = 1.0) -> Dict[str, Any]:
        """Add a toxic to a proxy (latency, bandwidth, timeout, etc.)."""
        resp = self.client.post(f"/proxies/{proxy_name}/toxics", json={
            "type": toxic_type,
            "stream": stream,
            "toxicity": toxicity,
            "attributes": attributes
        })
        resp.raise_for_status()
        return resp.json()

    def remove_toxic(self, proxy_name: str, toxic_name: str) -> None:
        """Remove a toxic from a proxy."""
        self.client.delete(f"/proxies/{proxy_name}/toxics/{toxic_name}")

    def disable_proxy(self, proxy_name: str) -> None:
        """Disable a proxy (simulates full connection cut)."""
        proxy = self.client.get(f"/proxies/{proxy_name}").json()
        proxy["enabled"] = False
        resp = self.client.post(f"/proxies/{proxy_name}", json=proxy)
        resp.raise_for_status()

    def enable_proxy(self, proxy_name: str) -> None:
        """Re-enable a proxy."""
        proxy = self.client.get(f"/proxies/{proxy_name}").json()
        proxy["enabled"] = True
        resp = self.client.post(f"/proxies/{proxy_name}", json=proxy)
        resp.raise_for_status()

    def reset(self) -> None:
        """Remove all toxics from all proxies."""
        self.client.post("/reset")

    def close(self) -> None:
        self.client.close()


# ---------- Fixtures ----------

@pytest.fixture(scope="session")
def toxiproxy() -> Generator[ToxiproxyClient, None, None]:
    """Session-scoped Toxiproxy client. Skips all chaos tests if unreachable."""
    if not _toxiproxy_reachable():
        pytest.skip("Toxiproxy not reachable (run docker compose -f docker-compose.yml -f docker-compose.chaos.yml up -d)")
    client = ToxiproxyClient()
    yield client
    client.reset()
    client.close()


@pytest.fixture(scope="session")
def redis_proxy(toxiproxy: ToxiproxyClient) -> Dict[str, Any]:
    """Create a Toxiproxy proxy for Redis: toxiproxy:26379 → sgr_redis:6379."""
    return toxiproxy.create_proxy(
        name="redis",
        listen="0.0.0.0:26379",
        upstream="sgr_redis:6379"
    )


@pytest.fixture(scope="session")
def qdrant_proxy(toxiproxy: ToxiproxyClient) -> Dict[str, Any]:
    """Create a Toxiproxy proxy for Qdrant: toxiproxy:26333 → sgr_qdrant:6333."""
    return toxiproxy.create_proxy(
        name="qdrant",
        listen="0.0.0.0:26333",
        upstream="sgr_qdrant:6333"
    )


@pytest.fixture(autouse=True)
def _reset_toxics(toxiproxy: ToxiproxyClient) -> Generator[None, None, None]:
    """Auto-reset all toxics after each test to prevent contamination."""
    yield
    toxiproxy.reset()
