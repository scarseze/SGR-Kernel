import os
import sys
import json
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from pydantic import BaseModel

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.runtime import CoreEngine
from core.container import Container
from core.logger import configure_logger, get_logger
from skills.calendar.handler import CalendarSkill
from skills.data_analyst.handler import DataAnalystSkill
from skills.filesystem.handler import ListDirSkill, ReadFileSkill
from skills.gost_writer.handler import GostWriterSkill
from skills.logic_rl.handler import LogicRLSkill
from skills.office_suite.handler import OfficeSkill
from skills.portfolio.handler import PortfolioSkill
from skills.research_agent.handler import ResearchSubAgent
from skills.rlm.handler import RLMSkill

# Import Skills
from skills.sglang_sim.handler import SGLangSkill
from skills.web_search.handler import WebSearchSkill

load_dotenv()
configure_logger()
logger = get_logger("api")

app = FastAPI(title="SGR Core Agent API", description="Universal Personal Agent Interface")

class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Whitelist health endpoints and docs
        if request.url.path.startswith("/health") or request.url.path.startswith("/docs") or request.url.path.startswith("/openapi.json"):
            return await call_next(request)

        # Use global engine redis if available
        if engine and engine.redis:
            try:
                client_ip = request.client.host if request.client else "unknown"
                # Rate Limit: 60 requests per minute per IP
                key = f"sgr:ratelimit:{client_ip}"
                
                # Atomic INCR
                count = await engine.redis.incr(key)
                
                # Set expiry on first request
                if count == 1:
                    await engine.redis.expire(key, 60)
                
                if count > 60:
                    logger.warning(f"Rate limit exceeded for {client_ip}")
                    return Response("429: Too Many Requests", status_code=429)
            except Exception as e:
                logger.error(f"Rate limiter failed: {e}")
        
        return await call_next(request)

app.add_middleware(RateLimitMiddleware)

class AgentRequest(BaseModel):
    query: str
    context: Optional[Dict[str, Any]] = None
    source_app: Optional[str] = "unknown"


class AgentResponse(BaseModel):
    result: str


engine: Optional[CoreEngine] = None


@app.on_event("startup")
async def startup_event():
    global engine
    logger.info("Starting SGR Core Server...")

    # Config Logic (Mirrors main.py)
    llm_config = {}
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    if deepseek_key:
        llm_config = {
            "base_url": os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
            "api_key": deepseek_key,
            "model": os.getenv("LLM_MODEL", "deepseek-chat")
        }

    # Auto-approve for API mode (or implement webhook callback later)
    async def api_approval(msg: str) -> bool:
        logger.info(f"⚡ Auto-approving action via API: {msg}")
        return True

    engine = CoreEngine(llm_config=llm_config, approval_callback=api_approval)
    await engine.init()

    # Register Skills
    engine.register_skill(SGLangSkill())
    engine.register_skill(PortfolioSkill())
    engine.register_skill(GostWriterSkill())
    engine.register_skill(CalendarSkill())
    engine.register_skill(RLMSkill())
    engine.register_skill(WebSearchSkill())
    engine.register_skill(OfficeSkill())
    engine.register_skill(DataAnalystSkill())
    engine.register_skill(ResearchSubAgent(llm_config))
    engine.register_skill(ReadFileSkill())
    engine.register_skill(ListDirSkill())
    engine.register_skill(LogicRLSkill())

    logger.info("Agent Engine Ready & Listening.")


@app.post("/v1/agent/process", response_model=AgentResponse)
async def process_request(req: AgentRequest):
    if not engine:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    # Inject Context into Prompt
    full_prompt = req.query
    full_prompt = req.query
    if req.context:
        # Smart Context Formatting
        ctx = req.context
        context_str = ""

        if "file_path" in ctx:
            context_str += f"CURRENT FILE: {ctx['file_path']}\n"

        if "selection" in ctx and ctx["selection"]:
            sel = ctx["selection"]
            context_str += (
                f"\nSELECTED CODE ({sel.get('start_line')}-{sel.get('end_line')}):\n```\n{sel.get('text', '')}\n```\n"
            )
        elif "content" in ctx:
            # If no selection, show partial content around cursor?
            # For now, let's truncate if too huge, or rely on LLM window
            content = ctx.get("content", "")
            if len(content) > 10000:
                content = content[:10000] + "...(truncated)"
            context_str += f"\nFILE CONTENT:\n```\n{content}\n```\n"

        # Fallback for generic context
        other_keys = {k: v for k, v in ctx.items() if k not in ["file_path", "content", "selection", "cursor_line"]}
        if other_keys:
            context_str += f"\nMETADATA: {other_keys}\n"

        full_prompt = f"CONTEXT FROM {req.source_app.upper()}:\n{context_str}\n\nUSER REQUEST: {req.query}"

    try:
        logger.info(f"Processing request from {req.source_app}")
        # The engine.run() method handles skill selection and execution
        result = await engine.run(full_prompt)
        return AgentResponse(result=result)
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health/db")
async def health_check_db():
    """
    Liveness probe for Database connection.
    """
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")

    try:
        from sqlalchemy import text
        # 1. Check Core Database (Postgres/SQLite)
        async with engine.db.async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        
        # 2. Check UI Memory Database (Alembic-managed)
        ui_memory = Container.get("ui_memory")
        ui_ok = True
        if ui_memory:
            ui_ok = await ui_memory.check_health()
        
        if not ui_ok:
             raise Exception("UI Memory Database health check failed")

        return {
            "status": "healthy",
            "core_db": "connected",
            "ui_db": "connected" if ui_memory else "not_found"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail=f"Database connection failed: {str(e)}")


@app.get("/health/swarm_topology")
async def swarm_topology():
    """Health-check endpoint for Swarm of Swarms monitoring."""
    # 1. Cache Check (Redis)
    if engine and engine.redis:
        try:
            cached = await engine.redis.get("sgr:api:cache:swarm_topology")
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Topology cache read failed: {e}")

    topology = {
        "status": "healthy",
        "engine_initialized": engine is not None,
        "compliance_level": os.environ.get("COMPLIANCE_LEVEL", "standard"),
        "registered_skills": [],
        "sub_swarm_capable": False
    }
    if engine:
        # Support both SwarmEngine (agents) and CoreEngine (skills)
        # CoreEngine has 'skills', SwarmEngine has 'agents'
        agents_source = getattr(engine, "agents", [])
        if not agents_source and hasattr(engine, "skills"):
            # Adapt CoreEngine skills to agent topology format
            class KernelAgentAdapter:
                def __init__(self, skills):
                    self.name = "Kernel"
                    self.skills = list(skills.values())
            agents_source = [KernelAgentAdapter(engine.skills)]

        for agent in agents_source:
            agent_info = {
                "name": agent.name,
                "skills": [s.name for s in agent.skills],
                "modalities": getattr(agent, "supported_modalities", ["text"]),
                "is_sub_swarm": getattr(agent, "is_sub_swarm", False)
            }
            topology["registered_skills"].append(agent_info)
            if getattr(agent, "is_sub_swarm", False):
                topology["sub_swarm_capable"] = True

    # 2. Cache Set (TTL 30s)
    if engine and engine.redis:
        try:
            await engine.redis.setex("sgr:api:cache:swarm_topology", 30, json.dumps(topology))
        except Exception as e:
            logger.warning(f"Topology cache write failed: {e}")
            
    return topology
