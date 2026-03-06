# System Overview

**Project**: SGR Kernel  
**Version**: 3.0.0 (Enterprise Swarm Tier)  
**Status**: Production-Ready  
**License**: MIT  

```text
┌──────────────────────────────────────────────┐
│                  USER / CLI                  │
│               Chainlit WebUI                 │
└──────────────────────┬───────────────────────┘
                       │ Chat Context
                       ▼
┌──────────────────────────────────────────────┐
│                 SWARM ENGINE                 │
│                                              │
│  • Agent Handoff / Transfer                  │
│  • Context & Memory Retention                │
│  • LLM Tool Calling (Skills)                 │
└───────────────┬──────────────────────────────┘
                │ delegates to
                ▼
┌──────────────────────────────────────────────┐
│             SPECIALIZED AGENTS               │
│                                              │
│  • RouterAgent (Triage)                      │
│  • KnowledgeAgent (RAG / DBs)                │
│  • PeftAgent (ML / Tuning)                   │
│  • DataAgent (Analytics)                     │
│  • WriterAgent (Docs)                        │
└───────────────┬──────────────────────────────┘
                │ executes
                ▼
┌──────────────────────────────────────────────┐
│                 SKILL LAYER                  │
│                                              │
│ knowledge_base (Lazy loads VectorDB)         │
│ peftlab (Lazy loads Optuna/Torch)            │
│ data_analyst                                 │
│ gost_writer                                  │
└──────────────────────────────────────────────┘
```

## 🎯 Purpose (Зачем это нужно)

The **SGR Kernel** is a specialized Agentic Operating System. Originally a legacy DAG step-executor, it has evolved into a full **Multi-Agent Swarm Architecture**. It bridges the gap between high-level reasoning (LLMs) and specialized execution (training, RAG, coding).

### Primary Goals
1.  **Multi-Agent Orchestration**: Autonomous collaboration between specialized Agent personas (Router, Analyst, ML Engineer) that dynamically hand off tasks to one another.
2.  **Decoupled & Lightweight Core**: Skills lazily load heavy dependencies (like `chromadb`, `optuna`). If the environment lacks them, the skill sleeps, but the Kernel never crashes.
3.  **Reproducible Science**: Ensuring every machine learning experiment (PEFT) is tracked and reproducible.

### Target Audience
*   **AI Researchers**: To run ablation studies and hyperparameter tuning (HPO) conversationally via the `PeftAgent`.
*   **LLM Engineers**: To query massive documentation via the decoupled `KnowledgeAgent` (RAG).
*   **Agent Developers**: To build new Agent Personas and integrate them into the Swarm.

---

## 🧱 System Scope

### ✅ What is in Scope (Что входит)
*   **Swarm Core**: Conversational orchestration, LLM interfacing, and `TransferToAgent` mechanisms.
*   **Enterprise Reliability Layer**: 
    * OTel Tracing & Metrics (Prometheus/Jaeger).
    * HitL execution pausing on Critic failures.
    * Active state checkpointing and memory timeline decay.
*   **V3 Enterprise Safeguards**:
    * Formal Output Verification (Proof Certificates).
    * Compliance Engine (152-FZ, GDPR data routing).
    * Economic Token Ledger & Budget Guards.
    * ModelRouter for Blue-Green HA swapping.
    * Automated Root Cause Analysis (RCA).
    * Privacy-Preserving Federated Learning.
*   **Agent Ecosystem**: Pre-configured Personas armed with specific capabilities.
*   **PEFT Lab**: Specialized stack for LoRA training, HPO, and exotic backends (Mamba/RWKV).
*   **Knowledge Base**: Decoupled RAG implementations.

### ❌ What is NOT in Scope (Что НЕ входит)
*   **Global Dependency Bloat**: We do NOT force `torch` or `chromadb` on a user who just wants to run a simple text-parsing agent.

---

## 🧩 Subsystems

### 1. Swarm Engine (`core/swarm.py`)
The brain of the system. Responsibilities:
*   **Loop Management**: Turns, tool calls, LLM history.
*   **Handoff**: Intercepts `TransferToAgent` signals and swaps the active persona's system prompt transparently.

### 2. Specialized Agents (`ui_app.py`, `core/agent.py`)
The Personas.
*   `RouterAgent`: The gateway. Greets the user, triages the intent, and transfers control.
*   `KnowledgeAgent`: Decoupled RAG. Has exclusive access to internal manuals and databases.
*   `PeftAgent`: ML Engineer. Runs sensitivity analysis and orchestrates training via PEFTlab.

### 3. Skill Layer (`skills/`)
The hands of the system.
*   `knowledge_base`: Lazy-loads VectorDB operations.
*   `peftlab`: Fine-tuning operations and Optuna HPO.
*   `handoff`: The dynamic `TransferSkill` that allows LLMs to "call" other agents.

---

## 🔁 Execution Flow (Как это работает)

1.  **Request**: User messages the UI ("Fix the learning rate on my Lora adapter").
2.  **Triage**: `RouterAgent` interprets the request and triggers `transfer_to_peftagent()`.
3.  **Handoff**: `SwarmEngine` catches the transfer, swaps the Active Agent to `PeftAgent`, and prepends the Peft instructions to the LLM context.
4.  **Execution**: `PeftAgent` calls `tune_hyperparameters` skill.
5.  **Completion**: `PeftAgent` formats the HPO report and transfers control back to the `RouterAgent` or waits for the user.

---

# Обзор Системы (System Overview)

**Проект**: SGR Kernel  
**Версия**: 3.0 (Enterprise Swarm Tier)  
**Статус**: Production-Ready  

## 🎯 Назначение (Purpose)

**SGR Kernel** — это Агентная Операционная Система. Эволюционировав из монолитного DAG-оркестратора, теперь это полноценный **Рой Агентов (Swarm)**.

### Основные Цели
1.  **Мультиагентность**: Узкоспециализированные агенты (Роутер, Аналитик, ML-инженер) общаются и динамически передают друг другу задачи.
2.  **Декаплинг (Легковесность)**: Тяжелые зависимости (VectorDB, PyTorch, Optuna) грузятся лениво (Lazy Load). Кернел стал молниеносным.
3.  **ML и RAG "Из коробки"**: Интегрированная база знаний и Лаборатория PEFT (Файн-тюнинг).

---

## 🧱 Границы Системы (System Scope)

### ✅ Что Входит (In Scope)
*   **Swarm Ядро**: Движок передачи контекста (`TransferToAgent`) и ведения истории.
*   **Enterprise Reliability Layer**: 
    * Телеметрия OTel (Prometheus/Jaeger).
    * Приостановка графа (HitL) при сбоях ИИ-Критика.
    * Активное сохранение стейтов и затухание устаревшей памяти (Decay).
*   **V3 Корпоративные Предохранители**:
    * Формальная верификация вывода (OutputSpec).
    * Комплаенс-маршрутизация (152-ФЗ, GDPR).
    * Экономический предохранитель бюджетов (Token Ledger).
    * Бесшовная подмена моделей (ModelRouter/Blue-Green).
    * Автоматический Root Cause Analysis (RCA).
    * Федеративное обучение с дифференциальной приватностью.
*   **Персоналии Агентов**: Готовые Агенты с настроенными системными промптами.
*   **PEFT Lab**: Стек для LoRA файн-тюнинга, HPO и работы с Mamba/RWKV.

---

## 🧩 Подсистемы (Subsystems)

### 1. Swarm Engine (`core/swarm.py`)
Мозг системы.
*   **Оркестрация**: Крутит цикл LLM и обрабатывает вызовы функций (Tool Calling).
*   **Передача контекста (Handoff)**: Бесшовно меняет активного агента, если был вызван скилл `transfer_to_X`.

### 2. Специализированные Агенты
Сформированная команда экспертов:
*   `RouterAgent`: Встречает пользователя, классифицирует интент и отправляет к специалисту.
*   `KnowledgeAgent`: Библиотекарь. Единолично владеет тяжелым RAG-поиском.
*   `PeftAgent`: ML-Инженер. Тюнит гиперпараметры через Optuna.
*   `DataAgent`: Аналитик. Работает с данными и браузером.

### 3. Слой Навыков (`skills/`)
Инструменты агентов.
*   `knowledge_base`: Изолированный векторный поиск.
*   `peftlab`: Конфигурация и запуск обучения моделей.
*   `handoff`: Механизм передачи мяча между агентами.

