# Event Catalog — SGR Kernel

> **Версия**: 3.0 | **Источник**: [`core/events.py`](file:///c:/Users/macht/SA/sgr_kernel/core/events.py), [`core/state_manager.py`](file:///c:/Users/macht/SA/sgr_kernel/core/state_manager.py)

SGR Kernel построен на **Event-Driven Architecture**. Каждое изменение состояния происходит **только** через публикацию события в `EventBus`. `StateManager` подписан на все события и детерминированно мутирует `ExecutionState`.

---

## Структура события (`KernelEvent`)

```python
class KernelEvent(BaseModel):
    event_id: str           # UUID, уникальный идентификатор
    type: EventType         # Тип события (см. таблицу ниже)
    payload: Dict[str, Any] # Данные, специфичные для типа
    request_id: str         # ID запроса (корреляция)
    timestamp: float        # Время создания (Unix)
    step_id: Optional[str]  # Для step-level событий
    actor: str              # "kernel" | "scheduler" | "orchestrator"
    span_id: Optional[str]          # OpenTelemetry span
    parent_event_id: Optional[str]  # Каузальная цепочка
    correlation_id: Optional[str]   # Для distributed tracing
```

---

## Каталог событий

### Lifecycle Events (Жизненный цикл выполнения)

| Event | Продюсер | Мутация `ExecutionState` | Payload |
|:------|:---------|:------------------------|:--------|
| `PLAN_CREATED` | `CoreEngine._generate_plan()` | `status → PLANNED`, инициализация `step_states` | `{plan_ir: PlanIR}` |
| `EXECUTION_STARTED` | `CoreEngine.run()` | `status → RUNNING` | `{}` |
| `EXECUTION_COMPLETED` | `ExecutionOrchestrator.execute()` | `status → COMPLETED` | `{}` |
| `EXECUTION_FAILED` | `ExecutionOrchestrator.execute()` | `status → FAILED` | `{error: str}` |
| `EXECUTION_ABORTED` | `CoreEngine.abort()` | `status → ABORTED` | `{reason: str}` |
| `EXECUTION_PAUSED` | `ApprovalMiddleware` | `status → PAUSED_APPROVAL` | `{step_id: str}` |

### Step Events (События шагов)

| Event | Продюсер | Мутация `StepState` | Payload |
|:------|:---------|:-------------------|:--------|
| `STEP_SCHEDULED` | `Scheduler` | *(логирование)* | `{step_id: str}` |
| `STEP_STARTED` | `StepLifecycleEngine` | `status → RUNNING`, `started_at = ts` | `{attempt: int}` |
| `STEP_COMPLETED` | `StepLifecycleEngine` | `status → COMMITTED`, `output = ...` | `{output: Any}` |
| `STEP_FAILED` | `StepLifecycleEngine` | `status → FAILED`, `failure = ...` | `{failure: FailureRecord}` |
| `STEP_RETRYING` | `StepLifecycleEngine` | `status → PENDING`, сброс `finished_at` | `{attempt: int}` |
| `STEP_VALIDATING` | `CriticEngine` | *(логирование)* | `{validator: str}` |

### Resource Events (Инфраструктурные)

| Event | Продюсер | Назначение |
|:------|:---------|:-----------|
| `CHECKPOINT_SAVED` | `CheckpointManager` | Фиксация точки восстановления |
| `TELEMETRY_RECORDED` | `TelemetryCollector` | Метрики производительности |
| `LEARNING_SIGNAL` | `LearningModule` | Обратная связь для self-improvement |

---

## Поток событий (Event Flow)

```mermaid
sequenceDiagram
    participant P as Producer (Engine/Scheduler)
    participant EB as EventBus
    participant ES as EventStore (SQLite)
    participant SM as StateManager
    participant S as Subscribers (Telemetry, Checkpoint...)

    P->>EB: publish(KernelEvent)
    EB->>ES: append(event) [PERSIST FIRST]
    EB->>SM: apply_event(state, event)
    SM->>SM: Idempotency check (processed_event_ids)
    SM->>SM: Deterministic state mutation
    EB->>S: notify subscribers (async, concurrent)
```

**Ключевой инвариант**: EventStore получает событие **перед** любой мутацией состояния. Это гарантирует возможность replay даже при сбое.

---

## Машина состояний: ExecutionStatus

```mermaid
stateDiagram-v2
    [*] --> CREATED
    CREATED --> PLANNED: PLAN_CREATED
    PLANNED --> RUNNING: EXECUTION_STARTED
    RUNNING --> COMPLETED: EXECUTION_COMPLETED
    RUNNING --> FAILED: EXECUTION_FAILED
    RUNNING --> ABORTED: EXECUTION_ABORTED
    RUNNING --> PAUSED_APPROVAL: EXECUTION_PAUSED
    RUNNING --> REPAIRING: repair triggered
    RUNNING --> ESCALATING: escalation triggered
    PAUSED_APPROVAL --> RUNNING: approval granted
    REPAIRING --> RUNNING: repair success
    ESCALATING --> RUNNING: tier escalation
```

## Машина состояний: StepStatus

```mermaid
stateDiagram-v2
    [*] --> PENDING
    PENDING --> READY: dependencies resolved
    READY --> RUNNING: STEP_STARTED
    RUNNING --> VALIDATING: execution complete
    VALIDATING --> CRITIC: critic check
    CRITIC --> COMMITTED: STEP_COMPLETED (pass)
    CRITIC --> REPAIR: critic fail (repairable)
    CRITIC --> FAILED: critic fail (not repairable)
    RUNNING --> FAILED: STEP_FAILED
    FAILED --> RETRY_WAIT: retry allowed
    RETRY_WAIT --> PENDING: STEP_RETRYING
    REPAIR --> RUNNING: repair applied
    RUNNING --> APPROVAL: HitL triggered
    APPROVAL --> RUNNING: approved
    APPROVAL --> FAILED: denied
```

---

## Гарантии

| Свойство | Механизм |
|:---------|:---------|
| **Idempotency** | `processed_event_ids` в `ExecutionState` — дублирующие события игнорируются |
| **Persistence-first** | `EventBus.publish()` записывает в `EventStore` **до** вызова подписчиков |
| **Replay** | `StateManager.reconstruct(events)` воссоздаёт состояние из лога событий |
| **Determinism** | Мутации строго определяются `event.type` + `event.payload`, без побочных эффектов |
| **Causal ordering** | `parent_event_id` и `correlation_id` обеспечивают каузальную трассировку |
