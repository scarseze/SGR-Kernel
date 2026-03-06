from core.compliance.engine import compliance_engine

@compliance_engine.register_rule(name="ru_152fz_data_locality")
def personal_data_never_leaves_ru(session_context: dict):
    """
    Enforces Federal Law 152-FZ (On Personal Data).
    If a session contains Russian PII, it must not be routed to servers
    located outside of the Russian Federation (e.g., standard OpenAI/Anthropic APIs).
    """
    contains_ru_pii = session_context.get("contains_ru_pii", False)
    llm_config = session_context.get("llm_config", {})
    
    if not contains_ru_pii:
        return True, "No Russian PII detected in session context."

    # If it contains RU PII, ensure the model is hosted on allowed infrastructure
    model = llm_config.get("model", "unknown").lower()
    base_url = llm_config.get("base_url", "").lower()
    
    # Example allowed secure/local models for PII
    allowed_models = ["ollama", "local", "yandex", "sber"]
    is_allowed = any(allowed in model for allowed in allowed_models) or \
                 "localhost" in base_url or "127.0.0.1" in base_url

    if is_allowed:
        return True, f"Model '{model}' is approved for local PII processing."
    else:
        return False, f"Model '{model}' is NOT authorized to process Russian PII. Data locality violation."
