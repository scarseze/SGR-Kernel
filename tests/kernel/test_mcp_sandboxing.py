import os
import sys

import pytest

from core.mcp_client import MCPClient
from skills.mcp_adapter import MCPSkillAdapter


@pytest.mark.asyncio
async def test_mcp_client_and_adapter():
    # Запускаем dummy_mcp_server.py как MCP сервер
    server_path = os.path.join(os.path.dirname(__file__), "dummy_mcp_server.py")
    
    client = MCPClient(sys.executable, [server_path])
    await client.connect()
    
    try:
        # Проверяем получение списка тулзов (tools/list)
        tools = await client.get_tools()
        assert len(tools) == 1
        
        tool_info = tools[0]
        assert tool_info["name"] == "dummy_calculator"
        
        # Создаем MCPSkillAdapter на базе полученной схемы
        adapter = MCPSkillAdapter(client, tool_info)
        
        # Проверяем, что Pydantic-схема корректно сгенерировалась
        InputSchema = adapter.input_schema
        assert "a" in InputSchema.model_fields
        assert "b" in InputSchema.model_fields
        
        # Готовим валидные параметры
        params = InputSchema(a=5, b=10)
        
        # Выполняем скилл (MCP call)
        result = await adapter.execute(params)
        
        # Строковое представление от MCP
        assert result == "15"
        
    finally:
        await client.close()
