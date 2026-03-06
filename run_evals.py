import os
import sys
from unittest.mock import AsyncMock

# Provide mock keys so the script can instantiate LLM wrappers
os.environ["LLM_API_KEY"] = "mock-key"
os.environ["OPENAI_API_KEY"] = "mock-key"

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from core.agent import Agent  # noqa: E402
from core.llm import LLMService  # noqa: E402
from core.metrics import AnswerRelevancyMetric, FaithfulnessMetric  # noqa: E402
from core.swarm import SwarmEngine  # noqa: E402
from evals.graders.deterministic import evaluate_exact_match  # noqa: E402
from evals.runner import BatchEvaluator, aggregate_results  # noqa: E402


async def main():
    # 1. Initialize core dependencies
    llm = LLMService(model="test-model-suite")
    engine = SwarmEngine(llm_config={"model": "test-model-suite"})

    agent = Agent(
        name="EvalAgent",
        instructions="Answer the user's questions clearly.",
        skills=[]
    )

    # 2. Setup the Evaluator with Graders
    # We mix LLM metrics and deterministic functions
    graders = [
        evaluate_exact_match,
        AnswerRelevancyMetric(llm, threshold=0.7),
        FaithfulnessMetric(llm, threshold=0.8)
    ]

    evaluator = BatchEvaluator(engine=engine, agent=agent, graders=graders)

    dataset_path = "evals/datasets/v0_baseline.jsonl"

    # Ensure the dataset exists
    if not os.path.exists(dataset_path):
        print(f"Dataset {dataset_path} not found.")
        sys.exit(1)

    print("Starting Evaluation Run using SwarmEngine and V0 Baseline dataset...")

    # 4. Run Batch with Mocked Engine and LLM to avoid real API costs for the baseline demo
    async def mock_execute(*args, **kwargs):
        messages = kwargs.get("messages", [])
        if not messages:
            return "Mocked Answer", agent, 0
        prompt = messages[-1]["content"].lower()
        if "france" in prompt:
            return "Paris", agent, 0
        if "2 + 2" in prompt:
            return "4", agent, 0
        if "translate" in prompt:
            return "Hola", agent, 0
        if "speed of light" in prompt:
            return "299,792,458 m/s", agent, 0
        if "ack" in prompt:
            return "ACK", agent, 0
        return "Unknown logic", agent, 0

    engine.execute = AsyncMock(side_effect=mock_execute)
    llm.generate = AsyncMock(return_value=("1.0", {}))  # Mocks metric LLM scoring

    records = await evaluator.run_batch(dataset_path)

    # 5. Aggregate Results globally and by slices
    aggregate_results(records)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
