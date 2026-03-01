import logging
import uuid
from typing import Any, Awaitable, Callable, Dict, Optional

from core.checkpoints import CheckpointManager
from core.critic import CriticEngine
from core.database import Database
from core.execution import (
    DependencyEdge,
    ExecutionState,
    ExecutionStatus,
    PlanIR,
    StepNode,
)
from core.execution.lifecycle import StepLifecycleEngine
from core.governance import GovernanceHooksBus
from core.llm import ModelPool
from core.planner import Planner
from core.reliability import ReliabilityEngine
from core.repair import RepairEngine
from core.replay import ReplayEngine
from core.skill_interface import Skill, SkillRuntimeAdapter
from core.memory import PersistentMemory
from core.memory_manager import MemoryManager
from core.summarizer import ConversationSummarizer
from core.telemetry_kernel import KernelTelemetry
from core.security import SecurityGuardian
from core.policy import PolicyEngine
from core.ui_memory import UIMemory

logger = logging.getLogger(__name__)

from core.container import Container
from core.event_bus import EventBus
from core.event_store import EventStore
from core.events import EventType, KernelEvent
from core.orchestrator import ExecutionOrchestrator
from core.state_manager import StateManager


class CoreEngine:
    """
    The main entry point for the SGR Kernel (Refactored v2).
    """

    VERSION = "2.0.0-alpha1"

    async def init(self):
        """Async initialization (DB tables, etc)."""
        await self.db.init_db()
        await self.ui_memory.initialize()

    def __init__(
        self,
        llm_config: Optional[Dict[str, Any]] = None,
        approval_callback: Optional[Callable[[str], Awaitable[bool]]] = None,
    ):
        logger.info(f"Initializing SGR Kernel v{self.VERSION} (Event-Driven)...")
        self._llm_config = llm_config or {}

        # 1. Infrastructure Setup
        self.db = Database()
        self.event_store = EventStore(self.db.async_session_factory)
        self.events = EventBus(event_store=self.event_store)
        self.policy = PolicyEngine()
        
        # Redis (Phase 5)
        import os
        import redis.asyncio as redis
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", 6379))
        if redis_host and redis_host != "mock_redis":
            self.redis = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
        else:
            self.redis = None
        
        self.checkpoints = CheckpointManager()
        self.telemetry = KernelTelemetry()

        # Register in Container
        Container.register("event_bus", self.events)
        Container.register("checkpoints", self.checkpoints)
        Container.register("telemetry", self.telemetry)
        Container.register("llm_config", self._llm_config)
        Container.register("redis", self.redis)
        
        self.ui_memory = UIMemory()
        Container.register("ui_memory", self.ui_memory)

        # 2. Wire up Event Subscribers (Observability)
        self.events.subscribe_all(self._on_any_event)
        
        self.security = SecurityGuardian()
        # 3. Core Services
        self.reliability = ReliabilityEngine()
        self.replay_engine = ReplayEngine()
        # self.db = Database() # Moved up
        self.model_pool = ModelPool(self._llm_config, replay_engine=self.replay_engine)
        
        # Memory Subsystem
        self.memory = PersistentMemory(self.db)
        self.summarizer = ConversationSummarizer(self.model_pool.fast)
        self.memory_manager = MemoryManager(self.memory, self.summarizer)

        # Planner expects an LLMService, not a dict
        self.planner = Planner(self.model_pool.heavy)

        self.skills: Dict[str, Skill] = {}
        self.skill_adapter = SkillRuntimeAdapter(self.skills)

        self.lifecycle = StepLifecycleEngine(
            skill_adapter=self.skill_adapter,
            reliability=self.reliability,
            critic=CriticEngine(self.model_pool.heavy),
            repair=RepairEngine(self.model_pool.heavy),
            hooks=GovernanceHooksBus(),
        )
        Container.register("lifecycle", self.lifecycle)

        self.orchestrator = ExecutionOrchestrator()

        # State tracking
        self.active_executions: Dict[str, ExecutionState] = {}
        self._approval_callback = approval_callback

    async def _on_any_event(self, event: KernelEvent):
        """Global event subscriber for state management and logging."""
        state = self.active_executions.get(event.request_id)
        if state:
            StateManager.apply_event(state, event)

            # Auto-checkpointing on critical events
            if event.type in [EventType.STEP_COMPLETED, EventType.PLAN_CREATED, EventType.EXECUTION_COMPLETED]:
                self.checkpoints.save_checkpoint(state, event.type.lower())

            # Telemetry
            if event.type == EventType.STEP_COMPLETED:
                self.telemetry.increment("skill_success_count")
            elif event.type == EventType.STEP_RETRYING:
                self.telemetry.increment("skill_retry_count")

    def register_skill(self, skill: Skill):
        if hasattr(skill, 'metadata') and isinstance(skill.metadata, dict):
            from core.types import SkillMetadata
            skill.metadata = SkillMetadata(**skill.metadata)
        self.skills[skill.name] = skill

    async def run(self, user_input: str, session_id: str = None) -> str:
        """
        Entry point for Kernel Execution.
        """
        # 1. Budget & Admission Check
        if hasattr(self.policy, "budget_ok") and not self.policy.budget_ok:
             return "Budget exceeded: denied by policy"
        
        if hasattr(self.policy, "check_budget") and not self.policy.check_budget():
             return "Budget exceeded: denied by policy"
             
        from core.tracing import new_span
        
        request_id = str(uuid.uuid4())[:12]
        
        # Start Root Span for this Request
        with new_span(trace_id=request_id):
            # 0. Security Input Validation (Defense in Depth)
            try:
                self.security.validate(user_input)
            except Exception as e:
                return f"🛡️ Security Violation: {str(e)}"

            state = ExecutionState(request_id=request_id, input_payload=user_input)
            
            # 1. Load Context (Memory)
            if session_id:
                await self.memory_manager.load_context(session_id, state)
            
            self.active_executions[request_id] = state

            try:
                # Step 2: Planning (Publish Event)
                plan_ir = await self._generate_plan(user_input)
                await self.events.publish(
                    KernelEvent(type=EventType.PLAN_CREATED, request_id=request_id, payload={"plan_ir": plan_ir.model_dump()})
                )
        
                # Step 3: Orchestration
                result = await self.orchestrator.execute(state)
                
                # 4. Save Context (Memory)
                if session_id:
                    # Save the interaction pair
                    await self.memory.add_message(session_id, "user", user_input)
                    await self.memory.add_message(session_id, "assistant", result)
                    
                return result
            finally:
                # CRITICAL: Cleanup execution state to prevent Memory Leak
                if request_id in self.active_executions:
                    del self.active_executions[request_id]

    async def resume(self, request_id: str) -> str:
        """Resume execution."""
        path = self.checkpoints.get_latest_checkpoint(request_id)
        if not path:
            return f"No checkpoint found for {request_id}"

        state, _ = self.checkpoints.load_checkpoint(path)
        self.active_executions[request_id] = state
        logger.info(f"♻️ Resuming {request_id}")

        return await self.orchestrator.execute(state)

    async def replay(self, request_id: str, up_to_event_id: Optional[str] = None) -> str:
        """
        Roll back state to a specific event and resume orchestration.
        """
        path = self.checkpoints.get_latest_checkpoint(request_id)
        if not path:
            return "No history found for replay."

        state, _ = self.checkpoints.load_checkpoint(path)

        # Delegate to ReplayEngine
        new_state = self.replay_engine.replay(state.event_log, up_to_event_id)
        self.active_executions[request_id] = new_state

        logger.info(f"⏪ Replaying {request_id} up to {up_to_event_id or 'end'}")
        return await self.orchestrator.execute(new_state)

    async def fork(self, request_id: str, from_event_id: str) -> str:
        """
        Fork execution into a new branch from a specific event.
        """
        path = self.checkpoints.get_latest_checkpoint(request_id)
        if not path:
            return "No history found for fork."

        state, _ = self.checkpoints.load_checkpoint(path)
        forked_state = self.replay_engine.fork(state.event_log, from_event_id)

        new_request_id = forked_state.request_id
        self.active_executions[new_request_id] = forked_state

        logger.info(f"🧬 Forked {request_id} into {new_request_id}")
        return await self.orchestrator.execute(forked_state)

    async def _generate_plan(self, user_input: str) -> PlanIR:
        skills_desc = "\n".join([s.name for s in self.skills.values()])
        raw_plan, _ = await self.planner.create_plan(user_input, skills_desc, "")

        steps = []
        edges = []
        for p_step in raw_plan.steps:
            from core.execution import RetryPolicy as ExecRetryPolicy
            rp_val = getattr(p_step.retry_policy, "value", str(p_step.retry_policy)).lower() if p_step.retry_policy else "none"
            if rp_val == "none":
                exec_rp = ExecRetryPolicy(max_attempts=1)
            elif rp_val == "aggressive":
                exec_rp = ExecRetryPolicy(max_attempts=5)
            else:
                exec_rp = ExecRetryPolicy(max_attempts=3)

            # Extract idempotency from skill metadata
            skill = self.skills.get(p_step.skill_name)
            is_idempotent = False
            if skill and hasattr(skill, "metadata"):
                # Handle both dict and SkillMetadata object
                metadata = skill.metadata
                if isinstance(metadata, dict):
                    is_idempotent = metadata.get("idempotent", False)
                else:
                    is_idempotent = getattr(metadata, "idempotent", False)

            node = StepNode(
                id=p_step.step_id,
                skill_name=p_step.skill_name,
                inputs_template=p_step.params,
                description=p_step.description,
                retry_policy=exec_rp,
                timeout_seconds=p_step.timeout_sec or 300.0,
                idempotent=is_idempotent,
            )
            steps.append(node)
            for dep in p_step.depends_on:
                edges.append(DependencyEdge(source_id=dep, target_id=node.id))
        return PlanIR(steps=steps, edges=edges, direct_response=raw_plan.direct_response)

    def abort(self, request_id: str, reason: str = "Manual Abort"):
        state = self.active_executions.get(request_id)
        if state:
            state.status = ExecutionStatus.ABORTED  # We still need a quick way to halt loop
            # Better to publish event, but orchestrator checks status
            logger.warning(f"Aborting {request_id}: {reason}")
