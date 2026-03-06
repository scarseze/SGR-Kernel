class ComplianceViolationError(Exception):
    """Raised when a regulatory compliance rule is violated before or during execution."""
    pass

class Rule:
    def __init__(self, name: str, evaluator: callable):
        self.name = name
        self.evaluator = evaluator

class ComplianceEngine:
    def __init__(self):
        self.rules = []
        self.audit_log = []

    def register_rule(self, name: str):
        def decorator(func):
            self.rules.append(Rule(name, func))
            return func
        return decorator

    def evaluate(self, session_context: dict):
        """
        Evaluates all registered rules against the given session context.
        Raises ComplianceViolationError if any rule fails.
        """
        for rule in self.rules:
            is_compliant, reason = rule.evaluator(session_context)
            
            # Log for audit trail
            log_entry = {
                "rule": rule.name,
                "status": "PASS" if is_compliant else "FAIL",
                "reason": reason
            }
            self.audit_log.append(log_entry)
            
            if not is_compliant:
                raise ComplianceViolationError(f"Compliance Violation [{rule.name}]: {reason}")
        
        return True

    def get_audit_trail(self) -> list:
        return self.audit_log

# Global compliance engine instance
compliance_engine = ComplianceEngine()
