import os

import pytest

from core.verification.tla_parser import InvariantViolationError, TLAParser, enforce_invariant

# Create a temporary mock TLA file for testing
MOCK_TLA_PATH = "mock_spec.tla"

@pytest.fixture(autouse=True)
def create_mock_tla():
    with open(MOCK_TLA_PATH, "w") as f:
        f.write("NoBudgetOverrun == total_spent <= max_budget\n")
        f.write("StateIsActive == status = \"active\"\n")
    yield
    if os.path.exists(MOCK_TLA_PATH):
        os.remove(MOCK_TLA_PATH)


def test_tla_parser_extraction():
    logic = TLAParser.extract_invariant_logic(MOCK_TLA_PATH, "NoBudgetOverrun")
    assert logic == "total_spent <= max_budget"
    
    # Test stub translator (converts single = to == for python eval)
    logic2 = TLAParser.extract_invariant_logic(MOCK_TLA_PATH, "StateIsActive")
    assert logic2 == "status == \"active\""


def test_enforce_invariant_pass():
    
    @enforce_invariant("NoBudgetOverrun", MOCK_TLA_PATH)
    def process_payment(total_spent: float, max_budget: float):
        return True
        
    # This should pass because 50 <= 100
    assert process_payment(50.0, 100.0) is True


def test_enforce_invariant_fail():
    
    @enforce_invariant("NoBudgetOverrun", MOCK_TLA_PATH)
    def process_payment_fail(total_spent: float, max_budget: float):
        return True
        
    # This should FAIL because 150 is NOT <= 100
    with pytest.raises(InvariantViolationError) as exc:
        process_payment_fail(150.0, 100.0)
        
    assert "Formally verified 'NoBudgetOverrun' failed" in str(exc.value)
    assert "precondition check" in str(exc.value)


def test_enforce_invariant_missing_spec():
    # If the file doesn't exist, it should gracefully fall back to just executing the function
    @enforce_invariant("FakeInvariant", "does_not_exist.tla")
    def simple_func():
        return "ok"
        
    assert simple_func() == "ok"
