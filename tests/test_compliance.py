import pytest
from core.compliance.engine import ComplianceEngine, ComplianceViolationError

# We use a fresh engine per test (not the global singleton) to avoid rule bleed
def make_engine_with_152fz():
    engine = ComplianceEngine()

    @engine.register_rule(name="ru_152fz_data_locality")
    def rule(session_context):
        contains_ru_pii = session_context.get("contains_ru_pii", False)
        if not contains_ru_pii:
            return True, "No PII."
        llm_config = session_context.get("llm_config", {})
        model = llm_config.get("model", "").lower()
        base_url = llm_config.get("base_url", "").lower()
        allowed = any(k in model for k in ["ollama", "local", "yandex", "sber"]) or \
                  "localhost" in base_url or "127.0.0.1" in base_url
        if allowed:
            return True, f"Model '{model}' approved."
        return False, f"Model '{model}' NOT authorized for RU PII."

    return engine


def make_engine_with_gdpr():
    engine = ComplianceEngine()

    @engine.register_rule(name="gdpr_data_minimization")
    def rule(session_context):
        jurisdiction = session_context.get("user_jurisdiction", "unknown")
        excessive_pii = session_context.get("excessive_pii", False)
        if jurisdiction.upper() not in ("EU", "EEA", "DE", "FR", "NL"):
            return True, "Not in GDPR scope."
        if excessive_pii:
            return False, "GDPR Violation: excessive PII detected."
        return True, "GDPR check passed."

    return engine


def test_152fz_passes_for_local_model():
    engine = make_engine_with_152fz()
    ctx = {
        "contains_ru_pii": True,
        "llm_config": {"model": "ollama/qwen2.5", "base_url": "http://localhost:11434"}
    }
    assert engine.evaluate(ctx) is True


def test_152fz_fails_for_openai():
    engine = make_engine_with_152fz()
    ctx = {
        "contains_ru_pii": True,
        "llm_config": {"model": "gpt-4", "base_url": "https://api.openai.com/v1"}
    }
    with pytest.raises(ComplianceViolationError) as exc_info:
        engine.evaluate(ctx)
    assert "NOT authorized" in str(exc_info.value)


def test_152fz_passes_when_no_pii():
    engine = make_engine_with_152fz()
    ctx = {
        "contains_ru_pii": False,
        "llm_config": {"model": "gpt-4"}
    }
    assert engine.evaluate(ctx) is True


def test_gdpr_fails_for_eu_with_excessive_pii():
    engine = make_engine_with_gdpr()
    ctx = {"user_jurisdiction": "EU", "excessive_pii": True}
    with pytest.raises(ComplianceViolationError) as exc_info:
        engine.evaluate(ctx)
    assert "GDPR Violation" in str(exc_info.value)


def test_gdpr_passes_for_non_eu():
    engine = make_engine_with_gdpr()
    ctx = {"user_jurisdiction": "US", "excessive_pii": True}
    assert engine.evaluate(ctx) is True


def test_audit_log_populated():
    engine = make_engine_with_152fz()
    ctx = {"contains_ru_pii": False, "llm_config": {"model": "gpt-4"}}
    engine.evaluate(ctx)
    log = engine.get_audit_trail()
    assert len(log) >= 1
    assert log[0]["status"] == "PASS"
    assert "152fz" in log[0]["rule"]
