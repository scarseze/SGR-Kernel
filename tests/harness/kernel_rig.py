"""
KernelTestRig — fluent harness for kernel compliance and integration tests.

Bypasses heavy CoreEngine.__init__ (DB, Qdrant, Ollama, RAG) via __new__,
wires only attributes needed by run() and _execute_step().

Usage:
    rig = KernelTestRig()
    rig.with_skill(FakeSkill(fail_times=2))
    result = await rig.run("test query")
    rig.assert_skill_calls("fake", 3)
"""

from typing import Any, List, Optional
from unittest.mock import AsyncMock, MagicMock

from core.execution import ExecutionState
from core.planner import ExecutionPlan, PlanStep
from core.runtime import CoreEngine
from core.security import SecurityGuardian
from core.trace import RequestTrace
from tests.fakes.fake_llm import FakeLLM
from tests.fakes.fake_planner import FakePlanner
from tests.fakes.fake_policy import FakePolicy


class _NoOpTraceManager:
    """TraceManager that doesn't write to filesystem."""

    def save_trace(self, trace: RequestTrace):
        self._last = trace

    def last_trace(self) -> Optional[RequestTrace]:
        return getattr(self, "_last", None)


class KernelTestRig:
    """Fluent builder for kernel test scenarios."""

    def __init__(self):
        import os
        from unittest.mock import MagicMock

        from core.container import Container
        
        # Ensure fresh container for isolation
        Container._registry = {}
        
        # Bypass Redis loading
        os.environ["REDIS_HOST"] = "mock_redis"
        
        # Real v2 engine
        eng = CoreEngine(llm_config={"api_key": "dummy"})
        
        # Mock EventStore to avoid sqlite errors in integration tests
        eng.event_store = MagicMock()
        eng.event_store.save_event = AsyncMock()
        eng.events.event_store = eng.event_store
        
        # Override Redis to force local execution
        eng.redis = None
        Container.register("redis", None)
        
        # --- Wire minimal attributes needed by run() ---
        eng.user_id = "test_user"
        eng.approval_callback = None
        eng.state = ExecutionState(request_id="rig_test", input_payload="")
        
        # Subsystems — fakes
        eng.llm = FakeLLM()
        
        # Re-wire Planner locally
        eng.planner = FakePlanner(engine=eng)
        
        # Policy is now mostly inside hooks/middlewares usually, 
        # but we mock policy for tests
        eng.policy = FakePolicy()
        
        eng.security = SecurityGuardian()
        eng.tracer = _NoOpTraceManager()

        # No-op DB session
        eng.db = MagicMock()
        eng.db.session = MagicMock(return_value=_AsyncCtx())

        # No-op memory manager
        eng.memory_manager = MagicMock()
        eng.memory_manager.augment_with_semantic_search = AsyncMock()

        # Skills (via v2 skill adapter)
        eng.skills = {}
        eng.skill_adapter.registry = eng.skills
        
        # Missing from some v2 tests: engine._resolve_string_template used by rig
        # V2 uses execution.resolution for this, so we bind it for compat
        from core.execution.resolution import resolve_inputs
        eng._resolve_string_template = lambda template, context: resolve_inputs({"v": template}, {"s1": {"output": context.get("s1", {}).get("x", {}).get("y", context.get("s1", {}))}}).get("v", template)
        # Note: The above lambda is still a bit hacky, but let's make it better:
        def _resolve_compat(template, context):
            # In rig tests, context is often {'s1': {'x': {'y': 7}}}
            # resolve_inputs expects state.skill_outputs as context
            return resolve_inputs({"v": template}, context).get("v", template)
        eng._resolve_string_template = _resolve_compat

        # Missing engine._execute_step used by rig (legacy test run_step)
        async def _execute_step(step_def, outputs, trace):
            # Shim run_step for v2
            from core.scheduler import TaskPayload
            payload = TaskPayload(
                step_id=step_def.id if hasattr(step_def, 'id') else step_def.step_id,
                skill_name=step_def.skill_name,
                inputs=step_def.params,
                request_id="test_step",
                attempt=1,
                trace_context={"trace_id": "test", "span_id": "test"},
                timeout=float(getattr(step_def, 'timeout_seconds', getattr(step_def, 'timeout_sec', 300.0)) or 300.0)
            )
            res = await eng.lifecycle.execute_task(payload)
            # Find the output event
            from core.events import EventType
            for e in res.events:
                if e.type == EventType.STEP_COMPLETED:
                    return e.payload.get("output")
            return None
            
        eng._execute_step = _execute_step

        self.engine = eng
        self._skills = []

    # ======================== Configuration ========================

    def with_skill(self, skill) -> "KernelTestRig":
        """Register a skill (real or fake)."""
        self.engine.register_skill(skill)
        self._skills.append(skill)
        return self

    def with_skills(self, skills: List) -> "KernelTestRig":
        for s in skills:
            self.with_skill(s)
        return self

    def with_plan(self, plan: ExecutionPlan) -> "KernelTestRig":
        """Override planner output."""
        self.engine.planner.plan = plan
        return self

    def with_steps(self, steps: List[PlanStep]) -> "KernelTestRig":
        """Shorthand: build plan from steps."""
        plan = ExecutionPlan(steps=steps, reasoning="test")
        return self.with_plan(plan)

    def with_direct_response(self, text: str) -> "KernelTestRig":
        """Planner returns direct response (no DAG)."""
        self.engine.planner.direct_response = text
        return self

    def with_budget(self, ok: bool) -> "KernelTestRig":
        """Control budget gate."""
        self.engine.policy.budget_ok = ok
        return self

    def with_middlewares(self, mws: List) -> "KernelTestRig":
        """Replace middleware stack (bridged to HOOKS)."""
        from core.governance import HOOK_AFTER_STEP, HOOK_BEFORE_STEP
        # Clear existing
        self.engine.lifecycle.hooks.hooks[HOOK_BEFORE_STEP] = []
        self.engine.lifecycle.hooks.hooks[HOOK_AFTER_STEP] = []
        
        for mw in mws:
            if hasattr(mw, 'before_execute'):
                 self.engine.lifecycle.hooks.register(HOOK_BEFORE_STEP, mw.before_execute)
            if hasattr(mw, 'after_execute'):
                 self.engine.lifecycle.hooks.register(HOOK_AFTER_STEP, mw.after_execute)
        return self

    def without_security(self) -> "KernelTestRig":
        """Replace security with no-op for isolated tests."""
        noop_sec = MagicMock()
        noop_sec.validate = MagicMock()
        noop_sec.validate_params = MagicMock()
        noop_sec.validate_output = MagicMock()
        self.engine.security = noop_sec
        return self

    # ======================== Execution ========================

    async def run(self, text: str = "test query") -> str:
        """Execute full run() pipeline."""
        return await self.engine.run(text)

    async def run_step(self, step_def: PlanStep, outputs: dict[str, Any] | None = None) -> Any:
        """Execute a single step directly (bypass planner/DAG)."""
        trace = RequestTrace(user_request="direct_step")
        outputs = outputs or {}
        return await self.engine._execute_step(step_def, outputs, trace)

    # ======================== Inspection ========================

    @property
    def last_trace(self) -> Optional[RequestTrace]:
        return self.engine.tracer.last_trace()

    @property
    def last_step(self):
        tr = self.last_trace
        if not tr or not tr.steps:
            return None
        return tr.steps[-1]

    @property
    def planner_calls(self) -> int:
        return self.engine.planner.create_plan_calls

    @property
    def policy(self) -> FakePolicy:
        return self.engine.policy

    # ======================== Assertions ========================

    def assert_skill_calls(self, skill, expected: int):
        """Assert a FakeSkill was called N times."""
        assert skill.calls == expected, f"{skill.name}: expected {expected} calls, got {skill.calls}"

    def assert_step_status(self, expected_status):
        """Assert last step trace has expected status."""
        step = self.last_step
        assert step is not None, "No step trace found"
        assert step.status == expected_status, f"Expected {expected_status}, got {step.status}"

    def assert_planner_not_called(self):
        assert self.planner_calls == 0, f"Planner was called {self.planner_calls} time(s)"

    def assert_planner_called(self, times: int = 1):
        assert self.planner_calls == times, f"Expected {times} planner call(s), got {self.planner_calls}"


class _AsyncCtx:
    """Fake async context manager for db.session()."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        pass
