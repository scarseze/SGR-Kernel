"""
Verification script for SGR Kernel Target Model (Event-Driven).
"""

import asyncio
import os
import sys
import uuid
from typing import Set

# Add syntax for SGR Kernel imports
sys.path.append(os.getcwd())

from core.checkpoints import CheckpointManager
from core.execution import ExecutionState, PlanIR, StepNode, StepState
from core.reliability import RecoveryAction, RetryDecisionEngine, RetryPolicy, SemanticFailureType
from core.replay import ReplayManager
from core.skill_interface import Skill, SkillContext, SkillResult


async def verify_target_model():
    print("🚀 Starting SGR Kernel Target Model Verification...")

    # 1. Setup Request
    request_id = str(uuid.uuid4())
    print(f"Request ID: {request_id}")

    # 2. Initialize State (Target Model)
    state = ExecutionState(request_id=request_id, user_input="Test Target Model")
    print("✅ ExecutionState initialized.")

    # 3. Define Plan (Target Model PlanIR)
    step1 = StepNode(id="step_1", skill="fs_read", inputs={"path": "test.txt"}, description="Read a file")
    plan = PlanIR(steps=[step1], edges=[])
    state.plan_ir = plan
    state.plan_id = plan.id
    print("✅ PlanIR created with StepNode.")

    # 4. Initialize Step Status
    state.initialize_step(step1.id)
    assert state.step_status[step1.id].state == StepState.PENDING
    print("✅ StepStatus initialized.")

    # 5. Define Mock Skill (Target Model Interface)
    class MockReadSkill(Skill):
        @property
        def name(self) -> str:
            return "fs_read"

        @property
        def capabilities(self) -> Set[str]:
            return {"read_fs"}

        async def execute(self, ctx: SkillContext) -> SkillResult:
            # Simulate work
            path = ctx.input_data.get("path")
            return SkillResult(output=f"Content of {path}")

    skill = MockReadSkill()
    print("✅ Mock Skill defined.")

    # 6. Execute Logic (Simulate Engine Loop)
    ctx = SkillContext(execution_state=state, llm_service=None, tool_registry={}, config={})
    ctx.input_data = step1.inputs

    state.update_step_state(step1.id, StepState.RUNNING)
    result = await skill.execute(ctx)

    state.skill_outputs[step1.id] = result.output
    state.update_step_state(step1.id, StepState.SUCCESS)

    print(f"✅ Skill Execution Result: {result.output}")
    assert state.step_status[step1.id].state == StepState.SUCCESS

    # 7. Reliability Test
    reliability = RetryDecisionEngine()
    policy = RetryPolicy(max_attempts=3, escalation_tiers=["gpt-4o"])

    # Case: Schema Fail -> Repair
    action = reliability.decide(policy, SemanticFailureType.SCHEMA_FAIL, attempts=1, confidence=1.0)
    print(f"✅ Reliability Test (Schema Fail): {action}")
    assert action == RecoveryAction.REPAIR or action == RecoveryAction.RETRY

    # Case: Low Confidence -> Escalate
    action_escalate = reliability.decide(policy, SemanticFailureType.LOW_CONFIDENCE, attempts=1, confidence=0.4)
    print(f"✅ Reliability Test (Low Confidence): {action_escalate}")
    assert action_escalate == RecoveryAction.ESCALATE_MODEL

    # 8. Checkpoint Test (Target Model)
    ckpt_manager = CheckpointManager(storage_path="temp_target_ckpt")
    ckpt_path = ckpt_manager.save_checkpoint(state, reason="step_complete")
    print(f"✅ Checkpoint saved: {ckpt_path}")

    loaded_state, ckpt_obj = ckpt_manager.load_checkpoint(ckpt_path)
    assert loaded_state.request_id == request_id
    assert ckpt_obj.reason == "step_complete"
    print("✅ Checkpoint loaded and validated.")

    # 9. Replay Test (Target Model)
    replay = ReplayManager(mode="record", storage_path="temp_target_tapes")
    replay.start_session(request_id)
    replay.record_interaction(
        prompt="hello", model="gpt-4", temperature=0.7, seed=42, response="world", usage={"tokens": 10}
    )
    replay.save_tape()
    print("✅ Replay tape saved.")

    # Cleanup
    import shutil

    if os.path.exists("temp_target_ckpt"):
        shutil.rmtree("temp_target_ckpt")
    if os.path.exists("temp_target_tapes"):
        shutil.rmtree("temp_target_tapes")

    print("\n🎉 All Target Model Verification Steps Passed!")


if __name__ == "__main__":
    asyncio.run(verify_target_model())
