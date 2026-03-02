import os
import sys
from typing import Any

import chainlit as cl
from core.logging_config import setup_logging

# Initialize Logging
setup_logging("core", host="sgr_fluent_bit")

# Add core to path so we can import modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.logger import get_logger
from core.telemetry import get_telemetry

logger = get_logger("ui")

# Start Prometheus metrics server
metrics_port = int(os.getenv("METRICS_PORT", 8001))
get_telemetry().start_metrics_server(metrics_port)

from core.swarm import SwarmEngine
from core.agent import Agent
from skills.handoff import TransferSkill
from core.ui_memory import UIMemory

def setup_swarm():
    llm_config = {}
    proxy_url = os.getenv("PROXY_URL")
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")

    if proxy_url:
        local_model = os.getenv("LOCAL_MODEL", "openai/qwen2.5:1.5b")
        llm_config = {"base_url": proxy_url + "/v1", "api_key": "dummy-key", "model": local_model}
    elif deepseek_key:
        llm_config = {"base_url": "https://api.deepseek.com", "api_key": deepseek_key, "model": "openai/deepseek-chat"}

    swarm = SwarmEngine(llm_config=llm_config)

    # Import skills
    from skills.data_analyst.handler import DataAnalystSkill
    from skills.web_search.handler import WebSearchSkill
    from skills.peftlab.handler import PEFTLabSkill
    from skills.gost_writer.handler import GostWriterSkill
    from skills.knowledge_base.handler import KnowledgeBaseSkill
    from skills.database.handler import DatabaseSkill
    from skills.filesystem.handler import WriteFileSkill
    
    # Define Agents
    knowledge_agent = Agent(
        name="KnowledgeAgent",
        instructions="You are the librarian and archivist. You search the internal knowledge base vector database using RAG to find matching documents to answer the user's questions.",
        skills=[KnowledgeBaseSkill()]
    )

    data_agent = Agent(
        name="DataAgent",
        instructions="You are a data scientist. You analyze data, build charts, explore the local database using SQL, and search the web for context. You can use your sql query skill to understand the tables and their data if asked about databases.",
        skills=[DataAnalystSkill(), WebSearchSkill(), DatabaseSkill()]
    )

    peft_agent = Agent(
        name="PeftAgent",
        instructions="You are an AI engineer specializing in PEFT and LoRA. You use PEFTlab to run sensitivity analysis and hyperparameter tuning.",
        skills=[PEFTLabSkill()]
    )

    writer_agent = Agent(
        name="WriterAgent",
        instructions="You format reports and generate GOST-compliant documents. You can also write content directly to markdown (.md) or mermaid (.mmd) files using your filesystem skill.",
        skills=[GostWriterSkill(), WriteFileSkill()]
    )

    router_agent = Agent(
        name="RouterAgent",
        instructions="You are the orchestrator. You greet the user, understand their request, and hand off control to the appropriate specialized agent. DO NOT answer complex questions yourself. Always transfer.",
        skills=[
            TransferSkill(knowledge_agent),
            TransferSkill(data_agent),
            TransferSkill(peft_agent),
            TransferSkill(writer_agent)
        ]
    )
    
    # Allow agents to hand back to router if they are done or stuck
    knowledge_agent.skills.append(TransferSkill(router_agent, "Transfer back to RouterAgent when you are finished or need a different specialist."))
    data_agent.skills.append(TransferSkill(router_agent, "Transfer back to RouterAgent when you are finished or need a different specialist."))
    peft_agent.skills.append(TransferSkill(router_agent, "Transfer back to RouterAgent when you are finished or need a different specialist."))
    writer_agent.skills.append(TransferSkill(router_agent, "Transfer back to RouterAgent when you are finished or need a different specialist."))

    all_agents = {
        "RouterAgent": router_agent,
        "KnowledgeAgent": knowledge_agent,
        "DataAgent": data_agent,
        "PeftAgent": peft_agent,
        "WriterAgent": writer_agent
    }

    return swarm, router_agent, all_agents

@cl.on_chat_start
async def start():
    swarm, router, all_agents = setup_swarm()
    ui_memory = UIMemory()
    session_id = cl.user_session.get("id")
    
    # Load history
    history, active_agent_name, transfer_count = ui_memory.load_session(session_id)
    ui_memory.cleanup_expired_sessions()
    
    active_agent = all_agents.get(active_agent_name, router)
    
    cl.user_session.set("swarm", swarm)
    cl.user_session.set("active_agent", active_agent)
    cl.user_session.set("messages", history)
    cl.user_session.set("ui_memory", ui_memory)
    cl.user_session.set("transfer_count", transfer_count)
    cl.user_session.set("all_agents", all_agents)

    if not history:
        await cl.Message(
            content="**SGR Swarm Orchestrator** готов к работе 🤖\n\nМои агенты (Router, Knowledge, Data, Peft, Writer) ждут ваших команд.",
            author="System",
        ).send()
    else:
        await cl.Message(
            content=f"**SGR Swarm Orchestrator** - Сессия восстановлена 🔄\n\nПродолжаем работу. Активный агент: **{active_agent.name}**",
            author="System",
        ).send()

@cl.on_message
async def main(message: cl.Message):
    swarm = cl.user_session.get("swarm")
    active_agent = cl.user_session.get("active_agent")
    messages = cl.user_session.get("messages")
    ui_memory = cl.user_session.get("ui_memory")
    session_id = cl.user_session.get("id")
    transfer_count = cl.user_session.get("transfer_count", 0)

    # Add user message
    messages.append({"role": "user", "content": message.content})

    msg = cl.Message(content="")
    await msg.send()

    async def swarm_event_handler(event_type, agent_name, payload):
        if event_type == "agent_start":
            step = cl.Step(name=f"🤖 {agent_name} is analyzing...")
            cl.user_session.set("current_step", step)
            await step.send()
        elif event_type == "tool_call":
            step = cl.Step(name=f"🛠️ {agent_name} -> {payload['tool']}")
            step.output = payload.get('args', '')
            await step.send()
        elif event_type == "transfer":
            step = cl.Step(name=f"🔄 Transfer (from {agent_name} to {payload['to_agent']})")
            step.output = payload['detail']
            await step.send()
            current_step = cl.user_session.get("current_step")
            if current_step:
                current_step.output = "Transferred focus."
                await current_step.update()
        elif event_type == "token":
            cl.user_session.set("has_token_stream", True)
            await msg.stream_token(payload['token'])

    try:
        # Run Swarm
        result, new_agent, new_transfer_count = await swarm.execute(
            active_agent, 
            messages,
            current_transfer_count=transfer_count,
            event_callback=swarm_event_handler
        )
        
        # Persist the newly active agent across chat turns
        cl.user_session.set("active_agent", new_agent)
        cl.user_session.set("transfer_count", new_transfer_count)
        
        # Update messages with assistant response and save session
        messages.append({"role": "assistant", "content": result})
        
        def audit_cb(sid, aan, tc):
            logger.info("session_saved", session_id=sid, active_agent=aan, transfer_count=tc)
            
        try:
            await ui_memory.async_save_session(
                session_id=session_id,
                history=messages,
                active_agent_name=new_agent.name,
                transfer_count=new_transfer_count,
                audit_callback=audit_cb
            )
        except Exception as e:
            logger.error("session_save_failed", session_id=session_id, error=str(e))
        
        # If tokens were streamed, msg.content is likely already populated natively in UI
        # We only override if it fell back to regular message
        if not cl.user_session.get("has_token_stream"):
            msg.content = result
        else:
            msg.content = result # this ensures markdown logic below will parse against the full text anyway
            cl.user_session.set("has_token_stream", False)

        import re
        matches = re.findall(r"\(file:///(.+?)\)", result)
        elements = []

        ALLOWED_ROOT = os.getenv("ATTACHMENTS_ROOT", os.path.abspath(os.path.dirname(__file__)))

        def is_safe_path(base_path, target_path):
            try:
                base_path = os.path.abspath(base_path)
                target_path = os.path.abspath(target_path)
                return os.path.commonpath([base_path, target_path]) == base_path
            except ValueError:
                return False

        for path in matches:
            if is_safe_path(ALLOWED_ROOT, path) and os.path.exists(path):
                name = os.path.basename(path)
                ext = name.split(".")[-1].lower()
                if ext in ["png", "jpg", "jpeg"]:
                    elements.append(cl.Image(path=path, name=name, display="inline"))
                else:
                    elements.append(cl.File(path=path, name=name))

        if elements:
            msg.elements = elements

    except Exception as e:
        import traceback
        traceback.print_exc()
        msg.content = f"**Error:** {str(e)}"

    await msg.update()
