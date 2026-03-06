import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

from core.agent import Agent
from core.swarm import SwarmEngine
from core.metrics import EvaluationMetric

# Setup basic logging for the runner
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("evals.runner")

class EvaluationRecord:
    def __init__(self, sample_id: str, input_data: Dict[str, Any], ground_truth: Dict[str, Any]):
        self.sample_id = sample_id
        self.input_data = input_data
        self.ground_truth = ground_truth
        self.prediction: Any = None
        self.latency_ms: int = 0
        self.scores: Dict[str, float] = {}
        self.passed: bool = False
        self.slices: List[str] = input_data.get("slices", ["all"])

class BatchEvaluator:
    def __init__(self, engine: SwarmEngine, agent: Agent, graders: List[Any]):
        self.engine = engine
        self.agent = agent
        self.graders = graders # List of grading functions or EvaluationMetric instances

    async def run_batch(self, dataset_path: str) -> List[EvaluationRecord]:
        records = self._load_dataset(dataset_path)
        logger.info(f"Starting evaluation on {len(records)} samples from {dataset_path}")
        
        for record in records:
            await self._evaluate_single(record)
            
        return records

    def _load_dataset(self, path: str) -> List[EvaluationRecord]:
        records = []
        if not os.path.exists(path):
            logger.error(f"Dataset not found: {path}")
            return records
            
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip(): continue
                data = json.loads(line)
                records.append(EvaluationRecord(
                    sample_id=data.get("id", "unknown"),
                    input_data=data.get("input", {}),
                    ground_truth=data.get("ground_truth", {})
                ))
        return records

    async def _evaluate_single(self, record: EvaluationRecord):
        logger.info(f"Evaluating sample: {record.sample_id}")
        start_time = time.time()
        
        # 1. Prediction (Execute Swarm)
        try:
            messages = record.input_data.get("messages", [])
            if not messages:
                messages = [{"role": "user", "content": record.input_data.get("query", "Empty query")}]
                
            res, _, _ = await self.engine.execute(
                starting_agent=self.agent,
                messages=messages,
                max_turns=3
            )
            record.prediction = res
        except Exception as e:
            logger.error(f"Prediction failed for {record.sample_id}: {e}")
            record.prediction = f"Error: {e}"
            
        record.latency_ms = int((time.time() - start_time) * 1000)
        
        # 2. Grading
        all_passed = True
        for grader in self.graders:
            try:
                if isinstance(grader, EvaluationMetric):
                    # It's an LLM metric from core.metrics
                    passed, reason, score = await grader.passes(
                        output=str(record.prediction),
                        context=str(record.input_data),
                        query=str(record.input_data.get("query", ""))
                    )
                    record.scores[grader.name] = score
                    if not passed:
                        all_passed = False
                else:
                    # It's an arbitrary grader function
                    score, passed = await grader(record)
                    record.scores[grader.__name__] = score
                    if not passed:
                        all_passed = False
            except Exception as e:
                logger.error(f"Grader {getattr(grader, 'name', grader.__name__)} failed: {e}")
                record.scores[getattr(grader, 'name', grader.__name__)] = 0.0
                all_passed = False
                
        record.passed = all_passed
        logger.info(f"Finished {record.sample_id}: Passed={record.passed}, Latency={record.latency_ms}ms")

def aggregate_results(records: List[EvaluationRecord]):
    """Aggregates scores globally and by data slice."""
    global_results = {"total": len(records), "passed": 0, "avg_latency": 0.0, "scores": {}}
    slice_results = {}
    
    if not records:
        print("No records to aggregate.")
        return
        
    total_latency = 0
    
    for r in records:
        if r.passed:
            global_results["passed"] += 1
        total_latency += r.latency_ms
        
        for metric, score in r.scores.items():
            global_results["scores"][metric] = global_results["scores"].get(metric, 0.0) + score
            
        for slc in r.slices:
            if slc not in slice_results:
                slice_results[slc] = {"total": 0, "passed": 0, "scores": {}}
            slice_results[slc]["total"] += 1
            if r.passed:
                slice_results[slc]["passed"] += 1
            for metric, score in r.scores.items():
                slice_results[slc]["scores"][metric] = slice_results[slc]["scores"].get(metric, 0.0) + score
                
    global_results["avg_latency"] = total_latency / len(records)
    for metric in global_results["scores"]:
        global_results["scores"][metric] /= len(records)
        
    for slc, data in slice_results.items():
        for metric in data["scores"]:
            data["scores"][metric] /= data["total"]
            
    # Print the report
    print("\n" + "="*50)
    print("EVALUATION REPORT")
    print("="*50)
    print(f"Total Samples: {global_results['total']}")
    print(f"Global Pass Rate: {(global_results['passed'] / global_results['total']) * 100:.2f}%")
    print(f"Average Latency: {global_results['avg_latency']:.2f}ms")
    print("Global Avg Scores:")
    for metric, score in global_results['scores'].items():
        print(f"  - {metric}: {score:.2f}")
        
    print("\n--- RESULTS BY DATA SLICE ---")
    for slc, data in slice_results.items():
        print(f"\nSlice: [{slc}]")
        print(f"  Samples: {data['total']}")
        print(f"  Pass Rate: {(data['passed'] / data['total']) * 100:.2f}%")
        for metric, score in data['scores'].items():
             print(f"  - {metric}: {score:.2f}")
    print("="*50 + "\n")
