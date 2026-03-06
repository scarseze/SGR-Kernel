import asyncio
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from core.ui_memory import UIMemory

async def test_generator_script():
    os.environ["MEMORY_DB_URL"] = "sqlite+aiosqlite:///data/memory.sqlite"
    memory = UIMemory()
    await memory.initialize()
    
    # 1. Insert a mock FAILED job into ui_memory
    print("Inserting mock failed job...")
    await memory.create_job(job_id="job-offline-test-123", org_id="default_org", payload={"task": "do something dangerous", "error": "LLM hallucinations led to unsafe command"})
    await memory.update_job_status(job_id="job-offline-test-123", status="FAILED")
    
    print("Job inserted and failed.")
    
    # 2. Run Reconciler Extraction (manually trigger it)
    print("Running reconciler extraction...")
    from core.reconciler import BackgroundReconciler
    from core.container import Container
    Container.register("ui_memory", memory)
    
    reconciler = BackgroundReconciler()
    await reconciler._extract_safety_cases()
    
    print("Extraction complete.")
    
    # 3. Check if scenario was saved
    scenarios = await memory.get_unresolved_scenarios()
    print(f"Found {len(scenarios)} unresolved scenarios.")
    for s in scenarios:
        print(f" - {s['scenario_id']}: {s['reason']}")
        
    print("Test finished successfully.")

if __name__ == "__main__":
    asyncio.run(test_generator_script())
