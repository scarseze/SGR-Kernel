import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


class ContextDehydrator:
    """
    State Sync Layer.
    When a model swap occurs (e.g. from 128k context to 8k context), we 
    must 'dehydrate' the conversation history so it fits the new target.
    """

    @classmethod
    def dehydrate(cls, history: List[Dict[str, Any]], target_max_tokens: int) -> List[Dict[str, Any]]:
        """
        Compresses the message history by keeping the System Prompt (index 0)
        and the N most recent turns, discarding the middle.
        
        (In a production implementation, this might call a fast local LLM to summarize the middle,
        but for V3 baseline, truncation of the middle is sufficient).
        """
        if not history:
            return []

        # Assuming rough token estimation: 1 word ~ 1.3 tokens. 
        # Using 4 chars per token as a very lazy proxy for speed without a tokenizer.
        def estimate_tokens(msgs):
            return sum(len(str(m.get("content", ""))) // 4 for m in msgs)

        current_tokens = estimate_tokens(history)
        
        # If it fits within an 80% safety margin of the target, no-op
        if current_tokens <= (target_max_tokens * 0.8):
            return history
            
        logger.info(f"Dehydrating context: {current_tokens} tokens into {target_max_tokens} target window.")

        # Always keep System Prompt (assumed to be index 0)
        system_prompt = history[0] if history and history[0].get("role") == "system" else None
        
        rehydrated = [system_prompt] if system_prompt else []
        
        # Keep the most recent messages that fit
        budget = int(target_max_tokens * 0.8)
        if system_prompt:
            budget -= len(str(system_prompt.get("content", ""))) // 4
            
        tail_messages = []
        for msg in reversed(history[1:]):
            msg_tokens = len(str(msg.get("content", ""))) // 4
            if budget - msg_tokens > 0:
                tail_messages.insert(0, msg)
                budget -= msg_tokens
            else:
                break
                
        # Insert dehydration marker
        if len(rehydrated) + len(tail_messages) < len(history):
            rehydrated.append({
                "role": "system",
                "content": "[SYSTEM: Conversation history dehydrated due to Model Swap/Context Window constraints.]"
            })
            
        rehydrated.extend(tail_messages)
        
        new_tokens = estimate_tokens(rehydrated)
        logger.info(f"Rehydrated context down to {new_tokens} tokens.")
        
        return rehydrated
