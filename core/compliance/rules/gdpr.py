from core.compliance.engine import compliance_engine

@compliance_engine.register_rule(name="gdpr_data_minimization")
def gdpr_no_unnecessary_pii(session_context: dict):
    """
    GDPR Article 5(1)(c): Data Minimisation.
    Checks that only the minimum necessary user data is submitted to the LLM.
    Denies execution if the context is flagged as containing excessive PII
    while in a GDPR-regulated jurisdiction.
    """
    user_jurisdiction = session_context.get("user_jurisdiction", "unknown")
    excessive_pii = session_context.get("excessive_pii", False)

    if user_jurisdiction.upper() not in ("EU", "EEA", "DE", "FR", "NL"):
        return True, f"Jurisdiction '{user_jurisdiction}' not in GDPR scope."

    if excessive_pii:
        return False, (
            "GDPR Violation: Session contains excessive PII for a GDPR-regulated user. "
            "Apply data minimization before invoking the LLM."
        )

    return True, f"GDPR data minimization check passed for jurisdiction '{user_jurisdiction}'."
