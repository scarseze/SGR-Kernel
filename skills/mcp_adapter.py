import json
import logging
from typing import Any, Dict, Optional, Type
from pydantic import BaseModel, create_model

from skills.base import BaseSkill
from core.types import SkillMetadata
from core.mcp_client import MCPClient

logger = logging.getLogger("mcp_adapter")

class MCPSkillAdapter(BaseSkill):
    """
    Адаптер, позволяющий подключать любой MCP сервер (внешний процесс) 
    как нативный Skill (плагин) внутри SwarmEngine.
    Это дает полную изоляцию исполнения для стороннего кода.
    """
    def __init__(self, client: MCPClient, tool_info: Dict[str, Any]):
        self._client = client
        self._tool_info = tool_info
        
        # Динамически генерируем Pydantic схему из MCP JSON Schema
        self._input_schema = self._build_pydantic_model(tool_info.get("name", "MCPTool"), tool_info.get("inputSchema", {}))

    def _build_pydantic_model(self, model_name: str, json_schema: Dict[str, Any]) -> Type[BaseModel]:
        """
        Конвертирует JSON Schema MCP сервера в Pydantic `BaseModel`.
        """
        properties = json_schema.get("properties", {})
        required = json_schema.get("required", [])
        
        fields = {}
        for prop_name, prop_details in properties.items():
            prop_type = Any
            if prop_details.get("type") == "string":
                prop_type = str
            elif prop_details.get("type") == "number":
                prop_type = float
            elif prop_details.get("type") == "integer":
                prop_type = int
            elif prop_details.get("type") == "boolean":
                prop_type = bool
            
            is_required = prop_name in required
            default_val = ... if is_required else None
            
            # (Type, Default) for create_model
            fields[prop_name] = (prop_type, default_val)
            
        return create_model(model_name, **fields)

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name=self.name,
            requires_human_approval=False, # MCP tools are isolated
            cost_type="mcp_isolated",
            category="mcp_plugins"
        )

    @property
    def name(self) -> str:
        return self._tool_info.get("name", "unknown_mcp_tool")

    @property
    def description(self) -> str:
        description = self._tool_info.get("description", "A tool provided by an isolated MCP server.")
        return f"[SANDBOXED/MCP] {description}"

    @property
    def input_schema(self) -> Type[BaseModel]:
        return self._input_schema

    async def execute(self, params: BaseModel, state: Optional[Any] = None) -> Any:
        """
        Проксирует выполнение в изолированный процесс MCP сервера по stdio JSON-RPC.
        """
        args_dict = params.model_dump()
        logger.info(f"Выполнение Sandboxed MCP-скилла '{self.name}' с аргументами: {args_dict}")
        result = await self._client.call_tool(self.name, args_dict)
        return result
