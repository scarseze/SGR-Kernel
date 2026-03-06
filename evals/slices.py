from typing import Dict, Any

def tag_slices(record: Dict[str, Any]) -> None:
    """
    Analyzes the input data and ground truth to assign Data Slices to the record.
    This modifies the dictionary in-place by adding/updating the 'slices' key list.
    """
    slices = ["all"]
    
    input_type = record.get("input", {}).get("type", "unknown")
    if input_type == "math":
        slices.append("math")
        
    # Check if the desired answer contains specific keywords indicating complexity
    gt_content = record.get("ground_truth", {}).get("content", "").lower()
    if "rag" in gt_content or "search" in gt_content:
        slices.append("requires_rag")
        
    if "pii" in gt_content or "social security" in gt_content:
        slices.append("has_pii")
        
    record["input"]["slices"] = slices
