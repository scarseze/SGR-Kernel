from core.routing.model_router import ModelRouter
from core.routing.state_sync import ContextDehydrator


def test_model_router_primary():
    router = ModelRouter()
    # Default without constraints should pick primary (gpt-4-turbo, 128k)
    route = router.get_best_route()
    assert route.name == "gpt-4-turbo"
    assert route.max_context == 128000


def test_model_router_fallback():
    router = ModelRouter()
    router.mark_down("primary")
    # Primary is down, should fallback to gpt-3.5-turbo
    route = router.get_best_route()
    assert route.name == "gpt-3.5-turbo"


def test_model_router_local_compliance():
    router = ModelRouter()
    # E.g. 152-FZ triggers this constraint
    route = router.get_best_route(requires_local=True)
    assert route.name == "ollama/qwen2.5"
    assert route.is_local is True


def test_model_router_all_down():
    router = ModelRouter()
    router.mark_down("primary")
    router.mark_down("fallback")
    router.mark_down("secure_local")
    # Total failure should trigger the hardcoded emergency fallback
    route = router.get_best_route()
    assert route.name == "fallback-none"


def test_context_dehydrator_no_op():
    history = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello"}
    ]
    # Huge target, shouldn't change
    dehydrated = ContextDehydrator.dehydrate(history, target_max_tokens=100000)
    assert len(dehydrated) == 2


def test_context_dehydrator_truncates_middle():
    # Construct a massive history
    history = [{"role": "system", "content": "You are a helpful assistant."}]
    # 50 messages, each ~250 tokens (1000 chars)
    for _i in range(50):
        history.append({"role": "user", "content": "A" * 1000})
        
    # Total tokens approx 50 * 250 = 12500. 
    # Target 8000 (Local Model), 80% budget is 6400 tokens.
    dehydrated = ContextDehydrator.dehydrate(history, target_max_tokens=8000)
    
    # Elements: System, Dehydration Marker, Tail Messages
    assert len(dehydrated) < len(history)
    assert dehydrated[0]["role"] == "system"
    assert "[SYSTEM: Conversation history dehydrated" in dehydrated[1]["content"]
    assert dehydrated[-1]["content"] == "A" * 1000
