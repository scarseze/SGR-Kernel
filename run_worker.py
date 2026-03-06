import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.logging_config import setup_logging

# Configure logging
# This validates that the worker can connect to Fluent Bit
logger = setup_logging("worker", host="sgr_fluent_bit")

from core.runtime import CoreEngine  # noqa: E402
from core.telemetry import get_telemetry  # noqa: E402


async def main():
    logger.info("👷 Worker Node Initialized (Standby Mode)")
    
    # Start Prometheus metrics server for worker (port 8002)
    metrics_port = int(os.getenv("METRICS_PORT", 8002))
    get_telemetry().start_metrics_server(metrics_port)
    
    # Init OpenTelemetry for worker tracing
    from core.telemetry import init_telemetry
    init_telemetry("sgr-worker")

    engine = None
    try:
        engine = CoreEngine()
        await engine.init()
        
        # Register Skills for Worker
        from skills.calendar.handler import CalendarSkill
        from skills.data_analyst.handler import DataAnalystSkill
        from skills.gost_writer.handler import GostWriterSkill
        from skills.office_suite.handler import OfficeSkill
        from skills.portfolio.handler import PortfolioSkill
        from skills.rlm.handler import RLMSkill
        from skills.sglang_sim.handler import SGLangSkill
        from skills.web_search.handler import WebSearchSkill

        engine.register_skill(SGLangSkill())
        engine.register_skill(PortfolioSkill())
        engine.register_skill(GostWriterSkill())
        engine.register_skill(CalendarSkill())
        engine.register_skill(RLMSkill())
        engine.register_skill(WebSearchSkill())
        engine.register_skill(OfficeSkill())
        engine.register_skill(DataAnalystSkill())
        
        logger.info("✅ Worker connected to Event Store & DB, Skills Registered")
    except Exception as e:
        logger.error(f"❌ Worker failed to connect to DB: {e}")

    logger.info("⚠️ Distributed Scheduler not yet active. Worker is listening for future tasks.")

    logger.info("🔌 Connecting to Redis for Distributed Tasks...")
    import json

    from core.execution.policy import StepResult
    from core.scheduler import TaskPayload
    from core.tracing import set_trace_context

    retry_delay = 1
    
    while True:
        try:
            # BLPOP blocks until a task is available
            # sgr:tasks is the queue
            if not engine or not engine.redis:
                logger.warning("⚠️ Engine/Redis not ready. Retrying...")
                # Re-init attempt?
                if not engine:
                    try:
                        engine = CoreEngine()
                        await engine.init()
                        engine.register_skill(DataAnalystSkill())
                        
                        logger.info("✅ Worker connected (Retry successful)")
                    except Exception as re_e:
                        logger.error(f"❌ Worker Re-init failed: {re_e}")
                        pass
                await asyncio.sleep(5)
                continue

            # redis.blpop returns (key, value)
            item = await engine.redis.blpop("sgr:tasks", timeout=5)
            if not item:
                continue
                
            queue_name, raw_payload = item
            logger.info(f"📨 Received Task: {len(raw_payload)} bytes")
            
            payload = TaskPayload.model_validate_json(raw_payload)
            
            # Set Trace Context
            set_trace_context(
                payload.trace_context.get("trace_id"),
                payload.trace_context.get("span_id")
            )
            
            # Execute Task
            # We use lifecycle.execute_task
            result: StepResult = await engine.lifecycle.execute_task(payload)
            
            # Push Result back
            # sgr:results:{request_id}
            # Find output in events if success
            output_data = None
            if result.success:
                for event in result.events:
                    if event.type == "STEP_COMPLETED" or event.type.value == "STEP_COMPLETED":
                        output_data = event.payload.get("output")

            # Set up events serialization so they can be parsed by Orchestrator
            events_data = [e.model_dump() for e in result.events] if result.events else []

            res_data = {
                "step_id": payload.step_id,
                "success": result.success,
                "output": output_data,
                "events": events_data
            }
            
            # Publish result to tenant-isolated result queue
            org_id = getattr(payload, "org_id", "default")
            await engine.redis.rpush(f"{org_id}:sgr:results:{payload.request_id}", json.dumps(res_data))
            logger.info(f"📤 Sent Result for {payload.step_id} (Tenant: {org_id})")
            
        except Exception as e:
            logger.error(f"Worker Loop Error: {e}")
            await asyncio.sleep(retry_delay)


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user.")
