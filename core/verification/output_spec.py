import json
import re
from typing import Any, Callable, Dict, List, Optional

from core.verification.certificate import ProofCertificate


class OutputSpecViolation(Exception):
    """Raised when an LLM output fails to satisfy its formal specification."""
    def __init__(self, spec_name: str, failed_check: str, details: str):
        self.spec_name = spec_name
        self.failed_check = failed_check
        super().__init__(f"OutputSpec [{spec_name}] violated check '{failed_check}': {details}")


class OutputSpec:
    """
    A chainable DSL for defining formal constraints on LLM outputs.

    Usage:
        spec = OutputSpec("safe_json_response") \\
            .requires_json() \\
            .forbids_pii() \\
            .max_length(5000)

        certificate = spec.validate(llm_output_text)
    """

    # Common PII patterns (RU + International)
    PII_PATTERNS = [
        r"\b\d{3}-\d{2}-\d{4}\b",           # US SSN
        r"\b\d{2}\s?\d{2}\s?\d{6}\b",        # RU Passport
        r"\b\d{3}-\d{3}-\d{3}\s?\d{2}\b",    # RU SNILS
        r"\bsk-[a-zA-Z0-9]{20,}\b",          # API keys
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",  # Email
    ]

    def __init__(self, name: str):
        self.name = name
        self._checks: List[Dict[str, Any]] = []

    def requires_json(self) -> "OutputSpec":
        """Output MUST be valid JSON."""
        def check(text: str) -> bool:
            try:
                json.loads(text)
                return True
            except (json.JSONDecodeError, TypeError):
                return False
        self._checks.append({"name": "requires_json", "fn": check, "desc": "Output must be valid JSON"})
        return self

    def forbids_pii(self) -> "OutputSpec":
        """Output MUST NOT contain recognizable PII patterns."""
        def check(text: str) -> bool:
            for pattern in self.PII_PATTERNS:
                if re.search(pattern, text):
                    return False
            return True
        self._checks.append({"name": "forbids_pii", "fn": check, "desc": "Output must not contain PII"})
        return self

    def max_length(self, n: int) -> "OutputSpec":
        """Output length MUST NOT exceed n characters."""
        def check(text: str) -> bool:
            return len(text) <= n
        self._checks.append({"name": f"max_length({n})", "fn": check, "desc": f"Output must be <= {n} chars"})
        return self

    def must_contain(self, keyword: str) -> "OutputSpec":
        """Output MUST contain a specific keyword."""
        def check(text: str) -> bool:
            return keyword.lower() in text.lower()
        self._checks.append({"name": f"must_contain({keyword})", "fn": check, "desc": f"Output must contain '{keyword}'"})
        return self

    def must_match_schema(self, schema_keys: List[str]) -> "OutputSpec":
        """Output MUST be JSON and contain all specified top-level keys."""
        def check(text: str) -> bool:
            try:
                data = json.loads(text)
                if not isinstance(data, dict):
                    return False
                return all(k in data for k in schema_keys)
            except (json.JSONDecodeError, TypeError):
                return False
        self._checks.append({
            "name": f"must_match_schema({schema_keys})",
            "fn": check,
            "desc": f"Output JSON must contain keys: {schema_keys}"
        })
        return self

    def custom(self, name: str, predicate: Callable[[str], bool]) -> "OutputSpec":
        """Add a custom predicate check."""
        self._checks.append({"name": name, "fn": predicate, "desc": f"Custom check: {name}"})
        return self

    def validate(self, text: str) -> ProofCertificate:
        """
        Run all registered checks against the text.
        Returns a ProofCertificate on success.
        Raises OutputSpecViolation on the first failure.
        """
        passed = []
        for check in self._checks:
            if not check["fn"](text):
                raise OutputSpecViolation(
                    spec_name=self.name,
                    failed_check=check["name"],
                    details=check["desc"]
                )
            passed.append(check["name"])

        return ProofCertificate(
            spec_name=self.name,
            output_hash=ProofCertificate.compute_hash(text),
            checks_passed=passed
        )
