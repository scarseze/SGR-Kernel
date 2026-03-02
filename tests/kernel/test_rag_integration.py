from unittest.mock import AsyncMock, patch

import httpx
import pytest

from skills.knowledge_base.handler import KnowledgeBaseSkill, SearchKnowledgeBase


@pytest.fixture
def skill():
    return KnowledgeBaseSkill()

@pytest.mark.asyncio
async def test_search_knowledge_base_success(skill):
    req = SearchKnowledgeBase(query="multi-agent", top_k=2)
    
    mock_response = httpx.Response(
        status_code=200,
        json={
            "results": [
                {
                    "content": "The SGR Kernel uses Multi-Agent Swarm architecture.",
                    "metadata": {"source": "architecture.md"},
                    "score": 0.95
                },
                {
                    "content": "Agents can delegate tasks.",
                    "metadata": {"source": "agent.md"},
                    "score": 0.88
                }
            ]
        },
        request=httpx.Request("POST", "http://localhost:8000/search")
    )
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        
        state = {"org_id": "tenant-abc", "trace_id": "trace-123"}
        result = await skill.execute(req, state)
        
        # Verify the mock was called
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert kwargs["json"] == {"query": "multi-agent", "top_k": 2}
        assert kwargs["headers"]["X-Tenant-ID"] == "tenant-abc"
        assert kwargs["headers"]["X-Trace-ID"] == "trace-123"
        
        # Verify the formatting
        assert "Knowledge Base Search Results" in result
        assert "**Result 1** (Source: `architecture.md`, Relevance Score: `0.95`):" in result
        assert "The SGR Kernel uses Multi-Agent Swarm architecture." in result
        assert "**Result 2** (Source: `agent.md`, Relevance Score: `0.88`):" in result

@pytest.mark.asyncio
async def test_search_knowledge_base_connection_error(skill):
    req = SearchKnowledgeBase(query="test", top_k=1)
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.ConnectError("Connection refused")
        result = await skill.execute(req)
        
        assert "System Warning: The Knowledge Base is currently offline" in result

@pytest.mark.asyncio
async def test_search_knowledge_base_http_error(skill):
    req = SearchKnowledgeBase(query="test", top_k=1)
    
    mock_response = httpx.Response(
        status_code=500,
        content=b"Internal Server Error",
        request=httpx.Request("POST", "http://localhost:8000/search")
    )
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.HTTPStatusError("500 Server Error", request=mock_response.request, response=mock_response)
        result = await skill.execute(req)
        
        assert "Error: The CBR RAG Backend returned a HTTP 500" in result
