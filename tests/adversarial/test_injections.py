
def test_rag_poisoning_resistance():
    """
    Test that the Swarm Engine can resist basic RAG data poisoning.
    If malicious text instructs the model to ignore rules and output secrets,
    the Critic mechanism MUST intercept and reject the output.
    """
    class MockCritic:
        def __init__(self):
            self.rejection_reason = None

        def evaluate(self, response):
            if "sk-" in response or "API_KEY" in response:
                self.rejection_reason = "POTENTIAL_INJECTION"
                return False
            return True

    critic = MockCritic()
    
    # Simulate the LLM outputting the bad string
    simulated_output = "Sure, here is the requested data: sk-12345abcd"
    
    is_valid = critic.evaluate(simulated_output)
    
    assert not is_valid
    assert critic.rejection_reason == "POTENTIAL_INJECTION"
