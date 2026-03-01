# Integration: AI/ML Playbook

This document outlines how the **SGR Kernel** interacts with the `ai_ml_playbook` repository. 

The Playbook serves as your organization's declarative source of truth for ML experiments, while the SGR Kernel provides the autonomous execution engine that brings those playbooks to life.

## 1. The Strategy: Declarative Meets Autonomous

The `ai_ml_playbook` defines the **"What"** and **"Why"**:
*   Experiment specifications (`.yaml` or `.json` playbook files).
*   Data pipelines architectures.
*   Evaluation thresholds and compliance rules.

The SGR Kernel acts as the **"How"**:
*   It parses the playbook format using its internal Router.
*   It spawns Sub-Agents (via `ResearchAgent` or `LoRATrainer`) to execute the notebook/training jobs defined in the playbook.
*   It logs progress back against the playbook's tracking manifest.

## 2. Using Playbooks with the Kernel

To bridge the gap between a static playbook and an executing Kernel, you typically pass the playbook URI or JSON manifest directly as the `goal` to the core routing engine.

### Example Workflow

1.  **Define your playbook** in the `ai_ml_playbook` repo:
    ```yaml
    # playbook/fraud_detection_v2.yaml
    experiment_id: fd_v2_baseline
    objective: "Migrate fraud rules to LightGBM"
    data_source: "s3://clean/fraud-2023.parquet"
    evaluation:
      primary_metric: "ROC-AUC"
      threshold: 0.85
    ```

2.  **Submit to the Kernel**:
    ```bash
    python main.py --goal "Execute playbook fraud_detection_v2.yaml. Use the DataAnalyst skill to extract the data, then train a baseline."
    ```

3.  **Kernel Execution**:
    *   The Kernel reads the objective.
    *   It provisions a `SkillContext`.
    *   It loops over its Plan (Fetch Data $\to$ Validate $\to$ Train $\to$ Evaluate).
    *   It writes artifacts (the model weights and metrics) back to disk.

## 3. Best Practices for Playbook Compatibility

When writing custom Skills inside the SGR Kernel specifically meant to interact with playbooks:

*   **Idempotency is Critical**: Playbook tasks often fail halfway (e.g., OOM during training). If a Skill is marked `idempotent=True` in its Metadata, the SGR Kernel can safely retry that exact step of the playbook without corrupting state.
*   **Artifact Referencing**: Always emit the absolute paths of generated models or datasets in your `SkillResult.artifacts`. This allows the Kernel to properly track the provenance of the Playbook's outputs.
*   **Telemetry Headers**: When emitting traces (via the Kernel's `TelemetryMiddleware`), always inject the `experiment_id` from the playbook into the span attributes. This connects the Kernel's distributed trace back to the strategic tracking dashboard of the `ai_ml_playbook`.

---

# Russian Section / Русская Секция 🇷🇺

# Интеграция: AI/ML Playbook

В этом документе описывается, как **SGR Kernel** взаимодействует с репозиторием `ai_ml_playbook`.

Playbook (плейбук) служит в вашей организации декларативным источником истины для ML-экспериментов, в то время как SGR Kernel предоставляет автономный движок выполнения, который воплощает эти плейбуки в жизнь.

## 1. Стратегия: Декларативное встречает Автономное

`ai_ml_playbook` определяет **«Что»** и **«Зачем»**:
*   Спецификации экспериментов (плейбук-файлы `.yaml` или `.json`).
*   Архитектуры конвейеров данных (Data pipelines).
*   Пороги оценки и правила соответствия.

SGR Kernel действует как **«Как»**:
*   Парсит формат плейбука с помощью своего внутреннего Маршрутизатора (Router).
*   Порождает Под-Агентов (через `ResearchAgent` или `LoRATrainer`) для выполнения заданий по блокнотам/обучению, определенных в плейбуке.
*   Логирует прогресс обратно в отслеживающий манифест плейбука.

## 2. Использование плейбуков с ядром

Чтобы преодолеть разрыв между статичным плейбуком и исполняющимся ядром, вы обычно передаете URI плейбука или JSON манифест напрямую как `goal` (цель) в основной движок маршрутизации.

### Пример рабочего процесса

1.  **Определите ваш плейбук** в репозитории `ai_ml_playbook`:
    ```yaml
    # playbook/fraud_detection_v2.yaml
    experiment_id: fd_v2_baseline
    objective: "Migrate fraud rules to LightGBM"
    data_source: "s3://clean/fraud-2023.parquet"
    evaluation:
      primary_metric: "ROC-AUC"
      threshold: 0.85
    ```

2.  **Отправьте в ядро**:
    ```bash
    python main.py --goal "Execute playbook fraud_detection_v2.yaml. Use the DataAnalyst skill to extract the data, then train a baseline."
    ```

3.  **Выполнение ядром**:
    *   Ядро считывает цель.
    *   Создает `SkillContext`.
    *   Выполняет в цикле свой План (Сбор данных $\to$ Валидация $\to$ Обучение $\to$ Оценка).
    *   Записывает артефакты (веса модели и метрики) обратно на диск.

## 3. Лучшие практики для совместимости с плейбуками

При написании пользовательских навыков (Skills) внутри SGR Kernel, специально предназначенных для взаимодействия с плейбуками:

*   **Критичность идемпотентности**: Задачи плейбука часто обрываются на половине (например, OOM - нехватка памяти при обучении). Если навык помечен как `idempotent=True` в своих Метаданных, SGR Kernel может безопасно повторить этот самый шаг плейбука, не повредив состояние.
*   **Ссылочность артефактов**: Всегда выдавайте абсолютные пути сгенерированных моделей или датасетов в ваш `SkillResult.artifacts`. Это позволяет ядру правильно отслеживать происхождение результатов плейбука.
*   **Заголовки телеметрии**: При эмиссии трассировок (через ядерный `TelemetryMiddleware`), всегда внедряйте `experiment_id` из плейбука в атрибуты span'а. Это связывает распределенную трассировку ядра обратно со стратегическим дашбордом отслеживания в `ai_ml_playbook`.
