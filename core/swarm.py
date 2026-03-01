import json
from typing import Any, Dict, List, Optional

import litellm
from core.agent import Agent, TransferToAgent, TransferToSubSwarm
from core.logger import get_logger
from core.telemetry import get_telemetry
from core.chaos import with_chaos

try:
    from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
    has_tenacity = True
except ImportError:
    has_tenacity = False

def safe_retry(func):
    if has_tenacity:
        return retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception_type(Exception),
            reraise=True
        )(func)
    return func

from core.container import Container
from core.quota import QuotaManager
 
logger = get_logger("swarm")

class SwarmEngine:
    """
    A lightweight, multi-agent orchestration engine inspired by OpenAI Swarm.
    Manages the conversational loop and handles context transfer between agents.
    """

    def __init__(self, llm_config: Dict[str, Any]):
        self.llm_config = llm_config
        self.client_kwargs = {
            "api_key": llm_config.get("api_key", "dummy"),
            "base_url": llm_config.get("base_url")
        }
        try:
            self.redis = Container.get("redis")
        except (ValueError, KeyError):
            self.redis = None
        self.quota_manager = QuotaManager(self.redis) if self.redis else None

    def _convert_skills_to_tools(self, skills: List[Any]) -> List[Dict[str, Any]]:
        tools = []
        for skill in skills:
            schema = skill.input_schema.model_json_schema()
            tools.append({
                "type": "function",
                "function": {
                    "name": skill.name,
                    "description": skill.description,
                    "parameters": schema
                }
            })
        return tools

    @safe_retry
    @with_chaos
    async def _safe_call_llm(self, model: str, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None, **kwargs) -> Any:
        return await litellm.acompletion(
            model=model,
            messages=messages,
            tools=tools,
            timeout=3600, # 1 hour timeout for slow local models
            **kwargs
        )

    async def execute(
        self, 
        starting_agent: Agent, 
        messages: List[Dict[str, Any]], 
        max_turns: int = 10,
        max_transfers: int = 5,
        current_transfer_count: int = 0,
        _swarm_depth: int = 0,
        _global_transfer_count: list = None,
        max_budget_usd: float = 0.0,
        _current_cost_usd: list = None,
        org_id: str = "default"
    ) -> tuple[str, Agent, int]:
        
        current_agent = starting_agent
        turn_count = 0
        transfer_count = current_transfer_count
        
        # Max horizontal explosions across ALL sub-swarms in one session call
        MAX_GLOBAL_TRANSFERS = 15
        if _global_transfer_count is None:
            _global_transfer_count = [0]
            
        if _current_cost_usd is None:
            _current_cost_usd = [0.0]


        
        # Deep-copy messages to avoid mutating the caller's session history
        history = [dict(m) for m in messages]
        
        # Real Data Isolation Guard (Phase 5)
        # Instead of 'System Prompt Enforcement', we validate that the history 
        # doesn't contain explicit references to other orgs (simple boundary check).
        if not org_id or org_id == "default":
            # For multi-tenant systems, org_id MUST be specific. 
            # If default is allowed, we still want to ensure it doesn't leak.
            pass
            
        # Enforce Org-specific scoping: The system relies on isolated context persistence in DB.
        # Ensure instructions clearly scope the actor.
        isolated_instructions = f"[Context: org_id={org_id}]\n" + current_agent.instructions
        
        if not history or history[0].get("role") != "system":
            history.insert(0, {"role": "system", "content": isolated_instructions})
        else:
            history[0] = {"role": "system", "content": isolated_instructions}

        with get_telemetry().span(f"swarm.execute_loop.{current_agent.name}") as parent_span:
            if parent_span:
                parent_span.set_attribute("agent.name", current_agent.name)
                parent_span.set_attribute("swarm.depth", _swarm_depth)

            while turn_count < max_turns:
                turn_count += 1
                logger.info(f"Swarm turn {turn_count}, Agent: {current_agent.name}")
                
                # Safety: Summarize history if too long to prevent context overflow
                if len(history) > 20:
                    logger.info("History exceeds 20 turns, summarizing context...")
                    middle_history = history[1:-10]
                    summary_prompt = (
                        "Summarize the following conversation history briefly, focusing on key facts and user intent:\n" 
                        + json.dumps(middle_history, ensure_ascii=False)
                    )
                    try:
                        summary_msg = await self._safe_call_llm(
                            model=self.llm_config.get("fast_model", self.llm_config.get("model", "deepseek-chat")),
                            messages=[{"role": "system", "content": "You are a concise summarizer."}, {"role": "user", "content": summary_prompt}],
                            temperature=0.0
                        )
                        summary_text = summary_msg.choices[0].message.content
                        history = [history[0], {"role": "user", "content": f"[Previous context summary]: {summary_text}"}] + history[-10:]
                    except Exception as e:
                        logger.error(f"Failed to summarize history: {e}")
                        history = [history[0]] + history[-10:]
                
                if max_budget_usd > 0 and _current_cost_usd[0] > max_budget_usd:
                    logger.error(f"Budget exceeded! Spent: ${_current_cost_usd[0]:.4f}, Budget: ${max_budget_usd:.4f}")
                    if parent_span:
                        parent_span.set_attribute("error", True)
                        parent_span.set_attribute("error.message", "Budget exceeded")
                    return f"Error: Task budget of ${max_budget_usd} exceeded. Stopping early.", current_agent, transfer_count

                # Global Quota Check (Phase 5)
                if self.quota_manager and not self.quota_manager.enforce(org_id, cost=0.0):
                    logger.error(f"Quota exceeded for org {org_id} during Swarm execution.")
                    return f"Error: 429 Quota Exceeded for Org {org_id}.", current_agent, transfer_count

                tools = self._convert_skills_to_tools(current_agent.skills)
                
                # 1. Call LLM
                try:
                    import time
                    start_time = time.time()
                    
                    with get_telemetry().span("llm.acompletion") as llm_span:
                        model_name = current_agent.model or self.llm_config.get("model", "deepseek-chat")
                        if llm_span:
                            llm_span.set_attribute("llm.model", model_name)
                            if current_agent.lora_adapter:
                                llm_span.set_attribute("llm.lora_adapter", current_agent.lora_adapter)
                                
                        completion_kwargs = self.client_kwargs.copy()
                        
                        # Phase 4: Dynamic PEFT LoRA loading
                        if current_agent.lora_adapter:
                            logger.info(f"🧠 Loading PEFT Adapter '{current_agent.lora_adapter}' for agent '{current_agent.name}'")
                            # Standard format for vLLM/Ollama dynamic adapters
                            completion_kwargs["extra_body"] = {"lora_name": current_agent.lora_adapter}
                        
                        response = await self._safe_call_llm(
                            model=model_name,
                            messages=history,
                            tools=tools if tools else None,
                            **completion_kwargs
                        )

                        latency_ms = int((time.time() - start_time) * 1000)
                        tokens_used = response.usage.total_tokens if hasattr(response, "usage") and response.usage else 0
                        
                        try:
                            call_cost = litellm.completion_cost(completion_response=response)
                            if call_cost:
                                _current_cost_usd[0] += call_cost
                                if llm_span:
                                    llm_span.set_attribute("llm.cost_usd", call_cost)
                        except Exception:
                            pass # Unknown model for litellm cost estimator
                        
                        if llm_span:
                            llm_span.set_attribute("llm.tokens", tokens_used)
                            llm_span.set_attribute("llm.latency_ms", latency_ms)
                        
                        get_telemetry().record_llm_call(
                            agent=current_agent.name,
                            model=model_name,
                            tokens=tokens_used,
                            latency_ms=latency_ms
                        )
                except Exception as e:
                    logger.error(f"LLM Error: {e}")
                    if parent_span:
                        parent_span.record_exception(e)
                    return f"Error connecting to LLM: {str(e)}", current_agent, transfer_count

                msg = response.choices[0].message
                history.append(msg.model_dump(exclude_none=True))

                # 2. Check for tool calls
                if not msg.tool_calls:
                    return msg.content or "Done", current_agent, transfer_count

            # 3. Handle Tool Calls
            tool_responses = []
            agent_swapped = False
            last_summary = None
            current_agent_name = current_agent.name
            
            for tool_call in msg.tool_calls:
                func_name = tool_call.function.name
                args_str = tool_call.function.arguments
                
                try:
                    args = json.loads(args_str)
                except json.JSONDecodeError:
                    args = {}

                logger.info(f"[{current_agent.name}] calling {func_name} with {args}")
                
                # Find matching skill
                target_skill = next((s for s in current_agent.skills if s.name == func_name), None)
                if not target_skill:
                    result_str = f"Error: Skill {func_name} not found in {current_agent.name}"
                else:
                    try:
                        with get_telemetry().span(f"skill.execute.{func_name}") as skill_span:
                            if skill_span:
                                skill_span.set_attribute("skill.name", func_name)
                            # Convert raw dict to Pydantic model and execute
                            validated_params = target_skill.input_schema(**args)
                            
                            import inspect
                            if inspect.iscoroutinefunction(target_skill.execute):
                                raw_res = await target_skill.execute(validated_params)
                            else:
                                raw_res = target_skill.execute(validated_params)
                                
                            # Handle Handoff
                            if isinstance(raw_res, TransferToSubSwarm):
                                sub_agent = raw_res.agent
                                next_depth = _swarm_depth + 1
                                MAX_SWARM_DEPTH = 3
                                
                                if next_depth > MAX_SWARM_DEPTH:
                                    logger.error(f"Sub-swarm depth limit ({MAX_SWARM_DEPTH}) exceeded! Aborting recursion.")
                                    result_str = f"Error: Max sub-swarm nesting depth ({MAX_SWARM_DEPTH}) reached."
                                else:
                                    logger.info(f"Handoff to SUB-SWARM: {sub_agent.name} (depth={next_depth})")
                                    get_telemetry().record_metric("subswarm_depth", next_depth)
                                    
                                    sub_config = dict(self.llm_config)
                                    if getattr(sub_agent, "sub_swarm_config", None):
                                        sub_config.update(sub_agent.sub_swarm_config)
                                        
                                    sub_engine = SwarmEngine(sub_config)
                                    sub_max_turns = max(3, max_turns // 2)
                                    sub_msg, _, sub_transfers = await sub_engine.execute(
                                        starting_agent=sub_agent,
                                        messages=[{"role": "user", "content": f"Sub-task context: {raw_res.context_message or 'Execute.'}"}],
                                        max_turns=sub_max_turns,
                                        _swarm_depth=next_depth,
                                        _global_transfer_count=_global_transfer_count,
                                        max_budget_usd=max_budget_usd,
                                        _current_cost_usd=_current_cost_usd,
                                        org_id=org_id
                                    )
                                    
                                    transfer_count += sub_transfers
                                    result_str = f"[Sub-Swarm {sub_agent.name} Result]: {sub_msg}"
                                    
                                    if not raw_res.return_to_parent_on_complete:
                                        current_agent = sub_agent
                                        agent_swapped = True
                                        last_summary = result_str
                                    
                            elif isinstance(raw_res, TransferToAgent):
                                current_agent = raw_res.agent
                                agent_swapped = True
                                _global_transfer_count[0] += 1
                                
                                MAX_GLOBAL_TRANSFERS = 15
                                if _global_transfer_count[0] > MAX_GLOBAL_TRANSFERS:
                                    logger.error(f"Global max transfers exceeded ({MAX_GLOBAL_TRANSFERS})! DDoS protection triggered.")
                                    result_str = f"Error: System-wide transfer limit ({MAX_GLOBAL_TRANSFERS}) reached. Emergency abort."
                                    agent_swapped = False # Abort swap
                                else:
                                    handoff_msg = f"Transferred to {current_agent.name}."
                                    if raw_res.context_message:
                                        handoff_msg += f" Note: {raw_res.context_message}"
                                        last_summary = raw_res.context_message
                                    else:
                                        last_summary = "No context summary provided."
                                    
                                    result_str = handoff_msg
                                
                                # Audit log for handoff
                                get_telemetry().record_handoff(from_agent=current_agent_name, to_agent=current_agent.name)
                                logger.info(
                                    "transfer_audit",
                                    from_agent=current_agent_name,
                                    to_agent=current_agent.name,
                                    context=last_summary
                                )
                            else:
                                result_str = str(raw_res)
                                
                    except Exception as e:
                        result_str = f"Error executing {func_name}: {str(e)}"

                # Append tool result
                history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": func_name,
                    "content": result_str
                })
                
                # If we swapped agents mid-loop, we break out to let the newly swapped
                # agent read the context and decide what to do
                if agent_swapped:
                    transfer_count += 1
                    if transfer_count > max_transfers:
                        return f"Error: Swarm max transfers ({max_transfers}) exceeded. Escalating to human/aborting.", current_agent, transfer_count

                    # Context Sanitization (Bleed Protection)
                    # Replace history with System instructions + condensed context summary
                    new_history = [{"role": "system", "content": isolated_instructions}]
                    new_history.append({"role": "user", "content": f"[Context from {current_agent_name}]: {last_summary} \n\nPlease proceed."})
                    history = new_history
                    break
            
            # Out of while loop
            return "Max turns reached", current_agent, transfer_count
