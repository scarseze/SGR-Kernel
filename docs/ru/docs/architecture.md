# Architecture

## High-Level Agent Architecture

```mermaid
graph TD
    User[User / Client] -->|Message/Chat| WebUI[Chainlit UI]
    
    subgraph SwarmEngine [Swarm Orchestrator]
        State[Conversation History]
        LLM[LLM Backend]
    end
    
    WebUI -->|Execute| SwarmEngine
    
    SwarmEngine -->|Route| Router[RouterAgent]
    
    subgraph Specialists [Specialized Agents]
        Knowledge[KnowledgeAgent]
        Data[DataAgent]
        Peft[PeftAgent]
        Writer[WriterAgent]
    end
    
    Router -->|TransferSkill| Specialists
    Specialists -->|TransferSkill| Router
    
    subgraph Skills [Skill Modules]
        RAG[KnowledgeBaseSkill]
        Ana[DataAnalystSkill / WebSearch]
        PEFT[PEFTLabSkill]
        Gost[GostWriterSkill]
    end
    
    Knowledge --> RAG
    Data --> Ana
    Peft --> PEFT
    Writer --> Gost
    
    subgraph Heavy Dependencies [Decoupled Backends]
        VectorDB[(Qdrant / Chroma)]
        Optuna[Optuna HPO]
        Torch[PyTorch / CUDA]
    end
    
    RAG -.->|Lazy Load| VectorDB
    PEFT -.->|Lazy Load| Optuna
    PEFT -.->|Lazy Load| Torch
```

## ⚡ Abstract Execution Flow

```mermaid
sequenceDiagram
    actor User
    participant WebUI as Chainlit UI
    participant Engine as SwarmEngine
    participant Router as RouterAgent
    participant LLM
    participant KA as KnowledgeAgent
    participant Skill as KnowledgeBaseSkill

    User->>WebUI: User Message
    WebUI->>Engine: execute(active_agent, history)
    Engine->>Router: active_agent initiates generate
    Router->>LLM: generate
    LLM-->>Router: ToolCall(transfer_to_knowledgeagent)
    Router->>Engine: Handoff Skill executes, returns TransferToAgent
    Engine->>Engine: updates active_agent = KnowledgeAgent
    Engine->>Engine: updates history System Prompt
    Engine->>KA: active_agent initiates generate
    KA->>LLM: generate
    LLM-->>KA: ToolCall(knowledge_base_search)
    KA->>Skill: executes
    Skill->>Skill: dynamically load VectorDB dependencies
    Skill-->>Engine: Results appended to history
    KA->>User: generates text response
```

---

# Архитектура (Architecture)

## Высокоуровневая Архитектура Агента (Swarm)

*   **Swarm Engine**: Легковесный движок-оркестратор. Управляет историей диалога и бесшовно передает контекст между Агентами.
*   **RouterAgent**: Маршрутизатор. Анализирует запрос и решает, какому узкоспециализированному Агенту передать задачу.
*   **Specialized Agents**: 
    *   **KnowledgeAgent**: Владеет RAG (База знаний).
    *   **DataAgent**: Владеет аналитикой и веб-серфингом.
    *   **PeftAgent**: Владеет машинным обучением (PEFTlab, HPO).
    *   **WriterAgent**: Владеет форматированием ГОСТ.
*   **Skills (Навыки)**: Инструменты, которые привязаны к конкретному Агенту. Тяжелые зависимости (`chromadb`, `optuna`, `torch`) загружаются **лениво** (Lazy Load), чтобы не замедлять ядро.

---

## L8 Distinguished Guarantees, Invariants, & Constraints
The SGR Kernel architecture adheres to a rigorous set of formal invariants, specifically designed to survive adversarial conditions, noisy neighbors, and extreme contention:

*   **Eventual Progress Guarantees:** The system guarantees eventual progress under bounded contention $C$ despite up to 15% transaction abort rates under `SERIALIZABLE` DB isolation. This is enforced via strict max retry budgets with full jitter and fallback priority escalations.
*   **Admission Control (Multi-Dimensional DRF):** To prevent shared resource contention (e.g., GPU vs CPU workloads), Admission Control calculates quotas over a multi-dimensional resource vector (Dominant Resource Fairness) rather than relying on naive, uniform token buckets.
*   **SLO Isolation & Tail Amplification:** Explicit tail correlation modeling prevents storage/DB retries from geometrically amplifying total queue execution latencies, ensuring per-stage SLO limits.
*   **Failure Domain Decoupling:** The execution plane remains completely decoupled from DB availability during runtime. A database outage will only cause bounded execution duplication during recovery, never crashing in-flight compute nodes.
*   **Atomic S3 Protocol:** Because S3 pseudo-`RENAME` operations are inherently flawed (COPY+DELETE), atomic visibility relies strictly on versioned storage paths and atomic `_SUCCESS` commit markers.
*   **Formal Failure Model:** The system exclusively targets crash-stop resilience. It does not tolerate Byzantine errors, and it assumes eventual network and hardware recovery.

For an exhaustive architectural rationale, refer to:
*   [L8 Distinguished System Invariants](l8_distinguished_invariants.md)
*   [L8 Architecture Annex & Tradeoffs](L8_ARCHITECTURE_ANNEX.md)
