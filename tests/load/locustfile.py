from locust import HttpUser, task, between, events
import json
import uuid

class SwarmAPIUser(HttpUser):
    wait_time = between(1, 3)

    @task(3)
    def test_health_topology(self):
        """High frequency test: check topology"""
        with self.client.get("/health/swarm_topology", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Topology failed: {response.text}")

    @task(1)
    def test_agent_process(self):
        """Complex task: simulate a user request to the Swarm"""
        payload = {
            "query": "Hello, Swarm! What is your current topology?",
            "context": {
                "source_app": "locust_load_test",
                "request_id": str(uuid.uuid4())
            }
        }
        
        with self.client.post("/v1/agent/process", json=payload, catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if "result" in data:
                    response.success()
                else:
                    response.failure(f"Missing result key: {data}")
            else:
                response.failure(f"Process failed: {response.status_code} - {response.text}")

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print("Starting SGR Kernel Swarm API Load Test...")

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    print("Completed SGR Kernel Swarm API Load Test.")
