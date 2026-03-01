from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

class Agent(BaseModel):
    """
    An individual Agent definition within the Swarm.
    Each Agent has a specific role, instructions, and isolated skill set.
    """
    name: str = Field(..., description="Unique name of the agent, e.g., 'RouterAgent'")
    instructions: str = Field(
        ..., 
        description="System prompt defining the agent's persona and logic"
    )
    skills: List[Any] = Field(
        default_factory=list, 
        description="List of instantiated skills (functions) available to this agent."
    )
    
    # Optional specific sub-model to use, defaults to swarm's default
    model: Optional[str] = Field(default=None)
    
    # Optional PEFT/LoRA adapter to load dynamically when this agent is active
    lora_adapter: Optional[str] = Field(
        default=None, 
        description="Name of the PEFT LoRA adapter for this specialized agent."
    )
    
    supported_modalities: List[str] = Field(
        default_factory=lambda: ["text"],
        description="List of supported modalities, e.g., ['text', 'image', 'audio']"
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)

class SubSwarmAgent(Agent):
    """
    SGR Kernel v3.0 (Swarm of Swarms):
    An agent that acts as a router/entrypoint for an entire sub-swarm.
    When this agent is activated, it can encapsulate a complex, multi-agent
    inner loop before returning the final synthesized answer back to the parent swarm.
    """
    is_sub_swarm: bool = True
    sub_swarm_config: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional overriding configuration for the isolated sub-swarm engine."
    )
    model_config = ConfigDict(arbitrary_types_allowed=True)

class TransferToAgent(BaseModel):
    """
    Special return object from a Handoff Skill.
    If a skill returns this, the Swarm engine will catch it and swap the active agent.
    """
    agent: Agent = Field(..., description="The next agent to hand control over to.")
    context_message: Optional[str] = Field(
        default=None, 
        description="Optional reason or summary passed directly to the next agent."
    )
    
    model_config = ConfigDict(arbitrary_types_allowed=True)

class TransferToSubSwarm(TransferToAgent):
    """
    Handoff to a completely separate hierarchical sub-swarm, entering an isolated event loop.
    """
    agent: SubSwarmAgent = Field(..., description="The entrypoint SubSwarmAgent for the new hierarchical swarm.")
    return_to_parent_on_complete: bool = Field(
        default=True,
        description="If True, control returns to the previous agent once the sub-swarm concludes."
    )
