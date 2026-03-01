import os
import traceback
import uuid
from typing import Any, Dict

import httpx
import structlog

from core.circuit_breaker import CircuitBreakerOpenException, rag_circuit_breaker
from core.types import Capability, CostClass, RiskLevel, SkillMetadata
from skills.base import BaseSkill
from skills.knowledge_base.schema import SearchKnowledgeBase
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = structlog.get_logger(__name__)

# The RAG backend is an external microservice now.
CBR_RAG_API_URL = os.environ.get("CBR_RAG_API_URL", "http://localhost:8000")


class KnowledgeBaseSkill(BaseSkill[Any]):
    name = "knowledge_base"
    description = "Searches the internal semantic knowledge base (Vector DB) for documents, manuals, and previously embedded context matching the user's query."

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            capabilities=[Capability.REASONING, Capability.DB],
            risk_level=RiskLevel.LOW,
            cost_class=CostClass.CHEAP,
            side_effects=False,
            idempotent=True,
            requires_network=True,     # Now requires HTTP access to cbr_rag
            requires_filesystem=False,
        )

    @property
    def input_schema(self) -> type[SearchKnowledgeBase]:
        return SearchKnowledgeBase

    def is_sensitive(self, params: Any) -> bool:
        return False

    async def execute(self, params: Any, state: Any = None) -> str:
        
        # 1. Parameter parsing
        if isinstance(params, dict):
            req = SearchKnowledgeBase(**params)
        else:
            req = params

        tenant_id = state.get("org_id", "default") if state else "default"
        trace_id = state.get("trace_id", str(uuid.uuid4())) if state else str(uuid.uuid4())

        logger.info("searching_knowledge_base", query=req.query, top_k=req.top_k, backend=CBR_RAG_API_URL, tenant_id=tenant_id, trace_id=trace_id)

        @rag_circuit_breaker
        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
            reraise=True
        )
        async def fetch_rag():
            # Apply circuit breaker / timeout best practices
            # 5 second timeout per request, 3 retries max
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    f"{CBR_RAG_API_URL.rstrip('/')}/search",
                    json={"query": req.query, "top_k": req.top_k},
                    headers={
                        "X-Tenant-ID": tenant_id,
                        "X-Trace-ID": trace_id
                    }
                )
                resp.raise_for_status()
                return resp.json()

        try:
            # 2. HTTP Request to the decoupled RAG Backend
            data = await fetch_rag()

            # 3. Parse and format the results for the LLM context
            results = data.get("results", [])
            
            if not results:
                return f"No relevant information found in the knowledge base for query: '{req.query}'"

            output = ["### 📚 Knowledge Base Search Results\n"]
            for i, res in enumerate(results, 1):
                # We expect the `cbr_rag` backend to return a list of dictionaries 
                # usually containing `content` and `metadata`
                content = res.get("content", str(res))
                meta = res.get("metadata", {})
                
                source = meta.get("source", "Unknown Document")
                score = res.get("score", 0.0)
                
                output.append(f"**Result {i}** (Source: `{source}`, Relevance Score: `{score:.2f}`):")
                output.append(f"{content}\n")

            return "\n".join(output)

        except (httpx.ConnectError, httpx.TimeoutException):
            logger.error("cbr_rag_connection_failed", url=CBR_RAG_API_URL)
            return f"System Warning: The Knowledge Base is currently offline or timing out (tried {CBR_RAG_API_URL}). Please proceed using your general knowledge."
        except CircuitBreakerOpenException:
            logger.error("cbr_rag_circuit_breaker_open")
            return f"System Warning: The Knowledge Base is currently offline or timing out (tried {CBR_RAG_API_URL}). Please proceed using your general knowledge."
        except httpx.HTTPStatusError as e:
            logger.error("cbr_rag_http_error", status_code=e.response.status_code, text=e.response.text)
            return f"Error: The CBR RAG Backend returned a HTTP {e.response.status_code}: {e.response.text}"
        except Exception as e:
            logger.error("knowledge_base_error", error=str(e), trace=traceback.format_exc())
            return f"Failed to search knowledge base: {str(e)}"
