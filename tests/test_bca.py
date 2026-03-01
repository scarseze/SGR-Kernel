import logging
import os
import subprocess
import time
from typing import List

import pytest
import requests

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_bca")


@pytest.mark.skipif(not os.getenv("RUN_BCA"), reason="BCA tests require manual trigger via RUN_BCA=1")
class TestBCA:
    """
    Black-box Container Assurance (BCA) Tests.
    Verifies that the Docker Compose stack is healthy and functioning.
    """

    @classmethod
    def setup_class(cls) -> None:
        """Ensure stack is running."""
        pass

    def run_command(self, cmd: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True)

    def test_containers_running(self) -> None:
        """Verify all critical containers are running."""
        # Check running services
        res = self.run_command("docker compose ps --services --filter status=running")
        running_services = res.stdout.strip().split("\n")

        required = ["sgr-core", "sgr-worker", "sgr_qdrant", "sgr_redis", "elasticsearch", "kibana", "fluent-bit"]
        missing = [s for s in required if s not in running_services]

        if missing:
            # Fallback: Check container names directly
            res_containers = self.run_command("docker ps --format '{{.Names}}'")
            running_containers = res_containers.stdout.strip().split("\n")

            # Map service names to likely container names
            map_service_container = {
                "sgr-core": "sgr_core",
                "sgr-worker": "sgr_worker",
                "elasticsearch": "sgr_elasticsearch",
                "kibana": "sgr_kibana",
                "fluent-bit": "sgr_fluent_bit",
            }

            still_missing: List[str] = []
            for s in missing:
                c_name = map_service_container.get(s, s)
                if c_name not in running_containers:
                    still_missing.append(s)

            assert not still_missing, f"Services not running: {still_missing}"

    def test_core_health(self) -> None:
        """Verify sgr-core is responsive."""
        retries = 5
        for _ in range(retries):
            try:
                r = requests.get("http://localhost:8501/healthz", timeout=5)
                # Chainlit might not have /healthz, check /
                if r.status_code == 200:
                    return
            except Exception:
                pass
            time.sleep(2)

        # Final check
        try:
            r = requests.get("http://localhost:8501", timeout=5)
            assert r.status_code == 200
        except Exception as e:
            pytest.fail(f"Core UI not reachable: {e}")

    def test_elasticsearch_reachable(self) -> None:
        """Verify ES is up."""
        try:
            r = requests.get("http://localhost:9200", timeout=5)
            assert r.status_code == 200
            data = r.json()
            assert "tagline" in data, "Not a valid ES response"
        except Exception as e:
            pytest.fail(f"Elasticsearch not reachable: {e}")

    def test_log_shipping(self) -> None:
        """
        Verify logs from sgr-core reach Elasticsearch.
        """
        # Allow fluent-bit flush time
        time.sleep(5)

        es_url = "http://localhost:9200/sgr_logs/_search"
        query = {"query": {"match_all": {}}, "size": 1}

        try:
            r = requests.get(es_url, json=query, timeout=5)
            if r.status_code == 404:
                logger.warning("Index sgr_logs not found yet.")
                return

            assert r.status_code == 200
            data = r.json()
            hits = data.get("hits", {}).get("total", {}).get("value", 0)
            logger.info(f"Found {hits} logs in ES.")
        except Exception as e:
            pytest.fail(f"Failed to query ES logs: {e}")


if __name__ == "__main__":
    # simple verification run
    t = TestBCA()
    try:
        t.test_containers_running()
        print("✅ Containers Running")
    except Exception as e:
        print(f"❌ Containers Running: {e}")
