# 2. Memory Decay and Conflict Resolution

Date: 2026-03-06

## Status

Accepted

## Context

The agent orchestration system accumulates long-term "episodic" memories in a vector store and "semantic" summaries in the database. Over time, episodic memories grow unbounded, leading to irrelevant context retrieval. Furthermore, as a user's preferences or facts change over time, newly summarized information may contradict older summaries, causing confusion for the LLM during context injection.

## Decision

We introduced a two-pronged approach to memory reflection:
1. **Time Decay Mechanism**: A background worker periodically purges vectors older than a specific threshold (e.g., 30 days) from the vector database.
2. **Conflict Resolution via LLM**: When generating a new conversation summary, the system uses an LLM prompt to actively compare the new context against the existing summary. If a contradiction is detected, the prompt instructs the summarization agent to prioritize the newer facts.

## Consequences

- **Pros**: Context windows remain small and highly relevant. Contradicting preferences are smoothly updated without manual intervention.
- **Cons**: Requires additional LLM calls for conflict detection during the summarization phase, slightly increasing latency and cost. Time decay means very old but potentially relevant minor details might be lost if they were not captured in semantic summaries.
