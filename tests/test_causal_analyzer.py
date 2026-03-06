from core.debugging.causal_analyzer import CausalAnalyzer
from core.execution import ExecutionState, StepState, StepStatus


# Mock Failure object to simulate step errors
class MockFailure:
    def __init__(self, failure_type, error_message):
        self.failure_type = failure_type
        self.error_message = error_message


def build_mock_state(step_id: str, failure_type: str, error_message: str) -> ExecutionState:
    state = ExecutionState(request_id="trace_123", input_payload={})
    
    # Simulate failed step
    failed_step = StepState(step_id=step_id)
    failed_step.status = StepStatus.FAILED
    failed_step.failure = MockFailure(failure_type, error_message)
    
    state.step_states[step_id] = failed_step
    return state


def test_analyze_critic_failure():
    analyzer = CausalAnalyzer()
    state = build_mock_state("step_1", "CRITIC_FAIL", "Critic rejected response: output violated schema")
    
    rc = analyzer.find_root_cause(state)
    assert rc.component == "CriticEngine"
    assert "schema" in rc.reason
    assert "Improve the agent's prompt" in rc.fix_suggestion


def test_analyze_timeout_failure():
    analyzer = CausalAnalyzer()
    state = build_mock_state("step_2", "TIMEOUT", "ReadTimeout from litellm")
    
    rc = analyzer.find_root_cause(state)
    assert rc.component == "Network / LLM Provider"
    assert "timed out" in rc.reason
    assert "Increase step timeout" in rc.fix_suggestion


def test_analyze_budget_failure():
    analyzer = CausalAnalyzer()
    state = build_mock_state("step_3", "OTHER", "Error: Budget Exceeded. Spent: $1.00")
    
    rc = analyzer.find_root_cause(state)
    assert rc.component == "BudgetGuard"
    assert "token/USD threshold" in rc.reason
    assert "cheaper model" in rc.fix_suggestion


def test_analyze_compliance_failure():
    analyzer = CausalAnalyzer()
    state = build_mock_state("step_4", "OTHER", "Compliance Violation [ru_152fz]: Not authorized")
    
    rc = analyzer.find_root_cause(state)
    assert rc.component == "ComplianceEngine"
    assert "regulatory compliance" in rc.reason
    assert "152-FZ" in rc.fix_suggestion


def test_analyze_unknown_failure():
    analyzer = CausalAnalyzer()
    state = build_mock_state("step_5", "UNKNOWN", "Division by zero in custom tool")
    
    rc = analyzer.find_root_cause(state)
    assert rc.component == "StepExecution[step_5]"
    assert "division by zero" in rc.reason
    assert "Check tool implementation" in rc.fix_suggestion
