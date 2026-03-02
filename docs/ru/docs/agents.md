# AI/ML Playbook Manifest (AGENTS.md)

Welcome to the constitution of the AI/ML department. This file regulates the work of agents that create and maintain systems based on Large Language Models (LLM) integrated with the **SGR Kernel** platform.

## 1. Mission and Task-driven Development
We operate on the principles of **Task-driven development**, where a specific task (issue) acts as the Spec.
- **Experiments**: Every experiment (Fine-Tuning, RAG Eval) is formulated as a separate task with a hypothesis and expected metrics. The solution is merged into the Knowledge Base only after Evaluation.

## 2. Knowledge Management and Prompts as Code
In AI/ML, the prompt acts as the source code.
- All system prompts are stored in the repository and versioned (Git). Use `templates/prompt_template.json`.
- It is forbidden to alter prompts "on the fly" without a Review and passing Evaluation tests.

## 3. Sandboxed Execution and Reproducibility
Any agent skill must be executed via **SGR Kernel**:
- **Sandboxes**: Code execution (data processing, evaluation scripts) occurs exclusively within Docker sandboxes of the SGR Kernel.
- **Reproducibility**: Every action is saved in the WAL, all experiments are described by a `manifest.json` file, guaranteeing exact reproduction of the environment and the Swarm execution log.

## 4. Cost Management and Cost Awareness
LLMs are expensive (Compute/API tokens).
- It is mandatory to use **Resource Quotas** and **Approval Gates** within SGR Kernel. Agents must select a model based on cost-efficiency (balancing quality and price: GPT-5 / Claude for complex reasoning, Qwen / DeepSeek for routine tasks).
- Factor in Rate Limits when planning Swarm tasks.

## 5. Security and PII
- It is strictly forbidden to transmit PII (Personal Identifiable Information) to external LLMs via public APIs without prior Anonymization/Pseudonymization by the `Data Engineer` agent.
- Access to databases and RAG-vectors is strictly regulated via **Capability Enforcement (ACLs)** in SGR Kernel.

## 6. Feedback Loop
It is mandatory to collect and recycle failed examples (Thumbs down, RLHF) for Continuous Improvement. All incidents and "hallucinations" are logged into the Dataset for Red Teaming / Evaluators.

---

# Russian Section / Русская Секция 🇷🇺

# AI/ML Playbook Manifest (AGENTS.md)

Добро пожаловать в конституцию AI/ML отдела. Этот файл регламентирует работу агентов, создающих и поддерживающих системы на базе Large Language Models (LLM) с интеграцией платформы **SGR Kernel**.

## 1. Миссия и Task-driven разработка
Мы работаем по принципам **Task-driven development**, где конкретная задача (issue) является спецификацией (Spec).
- **Эксперименты**: Каждый эксперимент (Fine-Tuning, RAG Eval) оформляется как отдельная задача с гипотезой и ожидаемыми метриками. Решение заливается в Knowledge Base только после оценки (Evaluation).

## 2. Управление знаниями (Knowledge Management) и Prompts as Code
В AI/ML промпт равен исходному коду.
- Все системные промпты хранятся в репозитории и версионируются (Git). Используйте `templates/prompt_template.json`.
- Запрещено изменять промпты "на лету" без Review и прохождения Evaluation-тестов.

## 3. Sandboxed Execution и Воспроизводимость
Любой скилл агента должен исполняться через **SGR Kernel**:
- **Песочницы**: Запуск кода (data processing, evaluation scripts) происходит исключительно в Docker-песочницах SGR Kernel.
- **Воспроизводимость**: Каждое действие сохраняется в WAL, все эксперименты описываются файлом `manifest.json`, гарантирующим точное воспроизведение окружения и журнала выполнения Swarm.

## 4. Экономика и Управление затратами (Cost Awareness)
LLM стоит дорого (Compute/API tokens).
- Обязательно использование **Resource Quotas** и **Approval Gates** в SGR Kernel. Агенты должны выбирать модель по стоимости (баланс качества и цены: GPT-5 / Claude для сложных задач, Qwen / DeepSeek для рутины).
- Учитывайте лимиты (Rate Limits) в планировании Swarm-задач.

## 5. Безопасность и PII
- Запрещена передача PII (Personal Identifiable Information) в LLM по публичному API без предварительной очистки (Anonymization/Pseudonymization) агентом `Data Engineer`.
- Доступ к базам данных и RAG-векторам регламентируется через **Capability Enforcement (ACLs)** SGR Kernel.

## 6. Цикл обратной связи (Feedback Loop)
Обязателен сбор и переработка неудачных примеров (Thumbs down, RLHF) для непрерывного переобучения (Continuous Improvement). Все инциденты и "галлюцинации" фиксируются в Dataset для Red Teaming / Evaluators.
