from core.learning.federated import AggregatorNode, DifferentialPrivacyFilter, LearningPayload


def test_laplace_noise_injection():
    dp = DifferentialPrivacyFilter(epsilon=1.0, sensitivity=1.0)
    raw = LearningPayload("agent_1", "test_task", True, {"score": 10.0})
    
    anon1 = dp.anonymize_metrics(raw)
    anon2 = dp.anonymize_metrics(raw)
    
    # Check ID is stripped
    assert anon1.agent_id == "anonymized_swarm_node"
    
    # Check noise is added (incredibly unlikely to be exactly 10.0 or equal to each other)
    assert anon1.metrics["score"] != 10.0
    assert anon1.metrics["score"] != anon2.metrics["score"]


def test_aggregator_functionality():
    dp = DifferentialPrivacyFilter(epsilon=0.5)  # Add more noise
    aggregator = AggregatorNode()
    
    # Generate 1000 noisy samples of a true value (100.0)
    for i in range(1000):
        raw = LearningPayload(f"agent_{i}", "test", True, {"eval_score": 100.0})
        anon = dp.anonymize_metrics(raw)
        aggregator.receive_payload(anon)
        
    assert len(aggregator.pool) == 1000
    
    # Aggregate them
    results = aggregator.trigger_aggregation()
    
    # Differential Privacy property: The average of many noisy samples should 
    # strongly approximate the true average, despite individual privacy.
    # Laplace noise mean is 0. So average should be close to 100.0
    approximate_true_score = results.get("avg_eval_score", 0.0)
    
    assert 95.0 < approximate_true_score < 105.0
    assert len(aggregator.pool) == 0  # Pool cleared


def test_gradient_noise_injection():
    dp = DifferentialPrivacyFilter(epsilon=1.0, sensitivity=1.0)
    gradients = [1.0, 2.0, 3.0, 4.0, 5.0]
    raw = LearningPayload("agent_grad", "gradient_task", True, {"loss": 0.5}, gradients=gradients)
    
    anon = dp.anonymize_metrics(raw)
    
    # Gradients must exist and be the same length
    assert anon.gradients is not None
    assert len(anon.gradients) == len(gradients)
    
    # Each gradient should have noise added (extremely unlikely to match original)
    mismatches = sum(1 for a, b in zip(anon.gradients, gradients, strict=False) if a != b)
    assert mismatches == len(gradients)
    
    # Agent ID must be anonymized
    assert anon.agent_id == "anonymized_swarm_node"
