import pytest
import json
from core.verification.output_spec import OutputSpec, OutputSpecViolation
from core.verification.certificate import ProofCertificate


def test_requires_json_passes():
    spec = OutputSpec("json_test").requires_json()
    cert = spec.validate('{"key": "value"}')
    assert cert.verified is True
    assert "requires_json" in cert.checks_passed


def test_requires_json_fails():
    spec = OutputSpec("json_test").requires_json()
    with pytest.raises(OutputSpecViolation) as exc_info:
        spec.validate("This is not JSON")
    assert "requires_json" in str(exc_info.value)


def test_forbids_pii_passes():
    spec = OutputSpec("pii_test").forbids_pii()
    cert = spec.validate("This is a clean response with no sensitive data.")
    assert cert.verified is True


def test_forbids_pii_fails_on_email():
    spec = OutputSpec("pii_test").forbids_pii()
    with pytest.raises(OutputSpecViolation):
        spec.validate("Contact me at user@example.com for details.")


def test_forbids_pii_fails_on_api_key():
    spec = OutputSpec("pii_test").forbids_pii()
    with pytest.raises(OutputSpecViolation):
        spec.validate("Here is the key: sk-abc123def456ghi789jkl012mno345")


def test_max_length_passes():
    spec = OutputSpec("len_test").max_length(100)
    cert = spec.validate("Short response")
    assert cert.verified is True


def test_max_length_fails():
    spec = OutputSpec("len_test").max_length(10)
    with pytest.raises(OutputSpecViolation):
        spec.validate("This response is way too long for the spec")


def test_must_match_schema_passes():
    spec = OutputSpec("schema_test").must_match_schema(["name", "age"])
    cert = spec.validate(json.dumps({"name": "Alice", "age": 30, "extra": True}))
    assert cert.verified is True


def test_must_match_schema_fails():
    spec = OutputSpec("schema_test").must_match_schema(["name", "age"])
    with pytest.raises(OutputSpecViolation):
        spec.validate(json.dumps({"name": "Alice"}))  # Missing "age"


def test_chained_spec():
    spec = OutputSpec("full_contract") \
        .requires_json() \
        .forbids_pii() \
        .max_length(500) \
        .must_match_schema(["result", "status"])

    payload = json.dumps({"result": "OK", "status": "done"})
    cert = spec.validate(payload)
    assert cert.verified is True
    assert len(cert.checks_passed) == 4
    assert cert.output_hash == ProofCertificate.compute_hash(payload)


def test_certificate_hash_deterministic():
    text = "Hello, World!"
    h1 = ProofCertificate.compute_hash(text)
    h2 = ProofCertificate.compute_hash(text)
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex digest
