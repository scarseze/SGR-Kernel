# Architecture

## 🤖 High-Level Agent Architecture

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

*   **⚙️ Swarm Engine**: Lightweight orchestrator engine. Manages dialogue history and seamlessly passes context between Agents.
*   **🚦 RouterAgent**: The router. Analyzes the request and decides which highly specialized Agent to transfer the task to.
*   **👥 Specialized Agents**: 
    *   **🧠 KnowledgeAgent**: Owns RAG (Knowledge Base).
    *   **📊 DataAgent**: Owns analytics and web-surfing.
    *   **🔧 PeftAgent**: Owns machine learning (PEFTlab, HPO).
    *   **✍️ WriterAgent**: Owns formatting of reporting documents according to GOST 19 and 34.
*   **🛠️ Skills**: Tools that are bound to a specific Agent. Heavy dependencies (`chromadb`, `optuna`, `torch`) are loaded **lazily** (Lazy Load) so as not to slow down the kernel.

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

## 🛡️ L8 Distinguished Guarantees, Invariants, & Constraints
SGR Kernel's architecture contains a strict set of formal invariants, specifically designed to survive under chaos, "noisy neighbors" and extreme resource competition:

*   **📈 Eventual Progress Guarantees:** The system guarantees forward progress under bounded contention $C$, despite transaction abort rates up to 15% under `SERIALIZABLE` DB isolation. This is ensured by rigid retry budgets with full jitter and priority escalation.
*   **🚦 Admission Control (Multi-Dimensional DRF):** To prevent common resource contention (e.g. GPU vs CPU workloads), Admission Control calculates quotas over a multi-dimensional resource vector (Dominant Resource Fairness) rather than relying on naive token buckets.
*   **⏱️ SLO Isolation & Tail Amplification:** Explicit modeling of tail correlation prevents geometric latency amplification of queues due to storage/DB retries, guaranteeing SLO limits are met at every stage.
*   **🔌 Failure Domain Decoupling:** The execution plane remains completely independent of DB availability during runtime. A database failure will only trigger bounded execution duplication upon recovery, but will never cause active compute nodes to crash.
*   **📦 Atomic S3 Protocol:** Because S3 pseudo-operations `RENAME` are inherently vulnerable (COPY+DELETE), atomic visibility strictly relies on versioned bucket paths and atomic `_SUCCESS` commit markers.
*   **🔥 Formal Failure Model:** The system exclusively targets crash-stop resilience. It does not tolerate Byzantine errors and assumes eventual network and hardware recovery.

For a comprehensive architectural rationale, see:
*   [📑 L8 Distinguished System Invariants](l8_distinguished_invariants.md)
*   [⚖️ L8 Architecture Annex & Tradeoffs](L8_ARCHITECTURE_ANNEX.md)
