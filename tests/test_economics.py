import pytest

from core.economics.ledger import BudgetExceededError, BudgetGuard, TokenLedger


def test_token_ledger_tracking():
    ledger = TokenLedger()
    
    # Simulate API call
    ledger.add_usage("gpt-4", 1000, 500)  # Cost calculation: (1000/1000)*0.03 + (500/1000)*0.06 = 0.03 + 0.03 = 0.06
    
    summary = ledger.get_summary()
    assert summary["prompt_tokens"] == 1000
    assert summary["completion_tokens"] == 500
    assert summary["total_tokens"] == 1500
    assert summary["estimated_cost_usd"] == 0.06

    # Simulate free local API call
    ledger.add_usage("ollama", 5000, 1000)
    summary = ledger.get_summary()
    assert summary["total_tokens"] == 7500
    assert summary["estimated_cost_usd"] == 0.06 # Unchanged because ollama is free


def test_budget_guard_limit_exceeded():
    ledger = TokenLedger()
    guard = BudgetGuard(max_cost_usd=0.10, max_tokens=5000)
    
    # Should pass
    ledger.add_usage("gpt-4", 1000, 500)  # 0.06 usd, 1500 tokens
    guard.check_budget(ledger) # No raise
    
    # Should breach USD limit
    ledger.add_usage("gpt-4", 1000, 500)  # total 0.12 usd -> breaches max 0.10
    with pytest.raises(BudgetExceededError) as exc_info:
        guard.check_budget(ledger)
    assert "Budget limit exceeded" in str(exc_info.value)
    
def test_budget_guard_token_exceeded():
    ledger = TokenLedger()
    guard = BudgetGuard(max_cost_usd=10.0, max_tokens=2000)
    
    # Should pass
    ledger.add_usage("ollama", 1500, 0)
    guard.check_budget(ledger)
    
    # Should breach Token limit
    ledger.add_usage("ollama", 600, 0) # total 2100 -> breaches max 2000
    with pytest.raises(BudgetExceededError) as exc_info:
        guard.check_budget(ledger)
    assert "Token limit exceeded" in str(exc_info.value)
