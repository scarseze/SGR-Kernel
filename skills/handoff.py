from typing import Any, Dict
from pydantic import BaseModel, ConfigDict, Field

from core.agent import Agent, TransferToAgent
from core.types import Capability
from skills.base import BaseSkill, SkillMetadata

class TransferSchema(BaseModel):
    context_summary: str = Field(description="A concise summary of the conversation history, user's intent, and the reason for handoff. This will be the ONLY context the next agent receives, so be thorough but brief.")

class TransferSkill(BaseSkill[BaseModel]):
    """
    Dynamically generated skill to transfer control to another agent.
    """
    def __init__(self, target_agent: Agent, description_override: str = None):
        self.target_agent = target_agent
        self._name = f"transfer_to_{target_agent.name.lower()}"
        self._desc = description_override or f"Transfer control to {target_agent.name}. Use this when the user's request is better handled by {target_agent.name}."

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._desc

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(capabilities=[Capability.REASONING], side_effects=False)

    @property
    def input_schema(self) -> type[BaseModel]:
        return TransferSchema

    async def execute(self, params: TransferSchema, state: Any = None) -> TransferToAgent:
        # Returning this object triggers the Swarm Engine to swap agents
        # Pass the context_summary to the Swarm Engine via TransferToAgent
        return TransferToAgent(agent=self.target_agent, context_message=params.context_summary)
