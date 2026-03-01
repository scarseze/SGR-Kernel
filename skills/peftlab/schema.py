from typing import Optional, Literal
from pydantic import BaseModel, Field

class PEFTlabRequest(BaseModel):
    action: Literal["analyze_sensitivity", "tune_hyperparameters", "auto_benchmark", "train_final_model"] = Field(
        ...,
        description="Action to perform. 'auto_benchmark' runs comparative trials. 'train_final_model' launches final training."
    )
    dataset_path: str = Field(
        ...,
        description="Path to the JSONL dataset file. E.g. 'data/train.jsonl'"
    )
    base_model: str = Field(
        ...,
        description="Hugging Face model ID. E.g. 'meta-llama/Llama-2-7b-hf'"
    )
    max_samples: Optional[int] = Field(
        8,
        description="Number of samples to analyze (keep low for memory/speed on GPU, default 8). Used only for sensitivity."
    )
    n_trials: Optional[int] = Field(
        5,
        description="Number of Optuna trials to run for HPO. Used only for tuning."
    )
    selected_strategy: Optional[str] = Field(
        "attention_only",
        description="Target strategy (e.g. attention_only). Used only for tuning."
    )
    hyperparams: Optional[dict] = Field(
        None,
        description="Optimal hyperparameters selected by the user for 'train_final_model' execution."
    )
