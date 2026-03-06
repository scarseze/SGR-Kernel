import hashlib
import time
from dataclasses import dataclass, field
from typing import List


@dataclass
class ProofCertificate:
    """
    An irrefutable receipt proving that an LLM output was formally
    verified against a named specification before being passed downstream.
    """
    spec_name: str
    output_hash: str
    checks_passed: List[str]
    timestamp: float = field(default_factory=time.time)
    verified: bool = True

    @staticmethod
    def compute_hash(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
