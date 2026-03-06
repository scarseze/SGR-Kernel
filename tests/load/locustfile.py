import uuid

from locust import HttpUser, between, events, task


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

    @task(3)
    def test_health_db(self):
        """High frequency test: check database connection"""
        with self.client.get("/health/db", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"DB Health failed: {response.text}")

    @task(1)
    def test_agent_process(self):
        """Complex task: simulate a user request to the Swarm"""
        payload = {
            "query": "Hello, Swarm! What is your current topology? Return immediately without thinking.",
            "context": {
                "source_app": "locust_load_test",
                "request_id": str(uuid.uuid4()),
                "mock_execution": True  # Instruct simple agents to skip LLM if implemented
            }
        }
        
        headers = {"X-Mock-Execution": "true"}
        
        with self.client.post("/v1/agent/process", json=payload, headers=headers, catch_response=True) as response:
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
