from dataclasses import dataclass
from typing import Optional

from core.execution import ExecutionState, StepStatus


@dataclass
class RootCause:
    """Represents a diagnosed root cause of a workflow execution failure."""
    component: str
    reason: str
    fix_suggestion: str
    trace_id: Optional[str] = None


class CausalAnalyzer:
    """
    Examines an aborted or failed ExecutionState to find the root cause.
    Replaces "Something failed" with actionable insights.
    """

    def find_root_cause(self, state: ExecutionState) -> RootCause:
        # Default fallback
        rc = RootCause(
            component="Unknown",
            reason="Execution did not complete successfully.",
            fix_suggestion="Check the general logs.",
            trace_id=state.request_id
        )

        for step_id, step_state in state.step_states.items():
            if step_state.status == StepStatus.FAILED and step_state.failure:
                
                failure_type = getattr(step_state.failure, "failure_type", "")
                error_msg = getattr(step_state.failure, "error_message", "").lower()

                # 1. Critic / Validation Failures
                if failure_type == "CRITIC_FAIL" or "critic" in error_msg:
                    rc.component = "CriticEngine"
                    rc.reason = f"Step '{step_id}' failed semantic validation: {error_msg}"
                    rc.fix_suggestion = "Review the Critic's rejection reason. Improve the agent's prompt or tools."
                    break

                # 2. Timeout / Network Failures
                if "timeout" in error_msg or failure_type == "TIMEOUT":
                    rc.component = "Network / LLM Provider"
                    rc.reason = f"Step '{step_id}' timed out waiting for LLM or external API."
                    rc.fix_suggestion = "Increase step timeout, switch to a faster model, or check API connectivity."
                    break

                # 3. Budget / Economics
                if "budget exceeded" in error_msg or "token limit" in error_msg:
                    rc.component = "BudgetGuard"
                    rc.reason = f"Session exceeded allowed token/USD threshold during step '{step_id}'."
                    rc.fix_suggestion = "Increase maximum budget, use a cheaper model, or optimize prompt length."
                    break
                    
                # 4. Compliance
                if "compliance violation" in error_msg:
                    rc.component = "ComplianceEngine"
                    rc.reason = f"Blocked due to regulatory compliance: {error_msg}"
                    rc.fix_suggestion = "Ensure data routing complies with registered compliance rules (e.g., 152-FZ, GDPR)."
                    break

                # Generic Step Failure
                rc.component = f"StepExecution[{step_id}]"
                rc.reason = error_msg
                rc.fix_suggestion = "Check tool implementation for unhandled exceptions."
                break

        return rc
