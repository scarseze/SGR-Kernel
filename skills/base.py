from abc import ABC, abstractmethod
from typing import Any, Generic, Optional, Type, TypeVar

from pydantic import BaseModel

from core.types import SkillManifest, SkillMetadata  # New centralized types

__all__ = ["BaseSkill", "SkillManifest", "SkillMetadata"]

# Removed local SkillMetadata and SkillManifest classes to avoid duplication
# and enforce platform consistency.

InputT = TypeVar("InputT", bound=BaseModel)


class BaseSkill(ABC, Generic[InputT]):
    """
    Abstract Base Class for all capabilities (Skills).
    Each skill represents a specialized domain (formerly a separate agent).
    """

    # Manifest loaded from YAML
    manifest: Optional[SkillManifest] = None

    def set_rag(self, rag_service: Any):
        """Optional: Inject RAG Service if the skill needs it."""
        self.rag = rag_service

    @property
    @abstractmethod
    def metadata(self) -> SkillMetadata:
        """Structured metadata for routing and policy enforcement."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """The unique identifier for this skill (e.g., 'portfolio_manager')"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """A natural language description of what this skill does for the Router/Planner."""
        pass

    @property
    @abstractmethod
    def input_schema(self) -> Type[BaseModel]:
        """The Pydantic model defining the strict input structure this skill requires."""
        pass

    def is_sensitive(self, params: BaseModel) -> bool:
        """
        Return True if this action requires human approval.
        Override this in specific skills (e.g. for file deletion/writing).
        """
        return False

    @abstractmethod
    async def execute(self, params: InputT, state: "ExecutionState") -> Any:
        """
        Execute the skill logic asynchronously.

        Args:
            params: The validated instance of input_schema.
            state: The global agent state.

        Returns:
            A string summary or a StepResult object with structured data.
        """
        pass
