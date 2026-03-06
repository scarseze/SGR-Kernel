class BudgetExceededError(Exception):
    """Raised when an agent session exceeds its allocated token or dollar budget."""
    pass

class TokenLedger:
    """
    Tracks LLM token usage and estimates costs for a given session.
    """
    
    # Simple cost estimation lookup (USD per 1k tokens)
    PRICING = {
        "gpt-4": {"prompt": 0.03, "completion": 0.06},
        "gpt-3.5-turbo": {"prompt": 0.0015, "completion": 0.002},
        "ollama": {"prompt": 0.0, "completion": 0.0}, # Local is free
        "default": {"prompt": 0.01, "completion": 0.02}
    }

    def __init__(self):
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_cost_usd = 0.0

    def add_usage(self, model_name: str, prompt_tokens: int, completion_tokens: int):
        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens
        
        # Determine pricing tier
        tier = self.PRICING.get("default")
        for key, rates in self.PRICING.items():
            if key in model_name.lower():
                tier = rates
                break
                
        # Calculate cost
        cost = (prompt_tokens / 1000.0) * tier["prompt"] + (completion_tokens / 1000.0) * tier["completion"]
        self.total_cost_usd += cost

    def get_summary(self) -> dict:
        return {
            "prompt_tokens": self.total_prompt_tokens,
            "completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_prompt_tokens + self.total_completion_tokens,
            "estimated_cost_usd": round(self.total_cost_usd, 4)
        }


class BudgetGuard:
    """
    Monitors a TokenLedger and raises an exception if limits are breached.
    """
    def __init__(self, max_cost_usd: float = 0.5, max_tokens: int = 100000):
        self.max_cost_usd = max_cost_usd
        self.max_tokens = max_tokens

    def check_budget(self, ledger: TokenLedger):
        summary = ledger.get_summary()
        
        if summary["total_tokens"] > self.max_tokens:
            raise BudgetExceededError(
                f"Token limit exceeded! Used: {summary['total_tokens']}, Limit: {self.max_tokens}"
            )
            
        if summary["estimated_cost_usd"] > self.max_cost_usd:
            raise BudgetExceededError(
                f"Budget limit exceeded! Spent: ${summary['estimated_cost_usd']}, Limit: ${self.max_cost_usd}"
            )
