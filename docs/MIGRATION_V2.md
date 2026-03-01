# SGR Kernel v1.x -> v2 Migration Guide

The SGR Kernel architecture has evolved from a monolithic engine (`core.engine`) to an Event-Driven Architecture (`core.runtime`, `Container`, `EventStore`). While backward compatibility has been heavily preserved via adapters, updating your `skills/` to the native V2 API unlocks better telemetry, lifecycle hooks, and removes terminal warnings.

## 1. The `execute` Signature Migration

The most significant change for Skill Developers is the deprecation of the `(params, state)` signature in favor of a unified `SkillContext`.

### ❌ Legacy V1 Signature

```python
from core.execution import ExecutionState
from skills.base import BaseSkill

class LegacySkill(BaseSkill):
    # This will still work via the fallback adapter, but is deprecated
    def execute(self, params: MyInputSchema, state: ExecutionState) -> str:
        api_key = state.config.get("API_KEY")
        return "Success"
```

### ✅ Modern V2 Signature

The new standard expects an asynchronous execution context that wraps all necessary data (config, global state, tool registry). 

```python
from core.skill_interface import SkillContext, SkillResult
from skills.base import BaseSkill

class ModernSkill(BaseSkill):
    async def execute(self, ctx: SkillContext) -> SkillResult:
        # 1. Extract and validate parameters
        params = self.input_schema(**ctx.config)
        
        # 2. Access global state (if strictly necessary)
        api_key = ctx.execution_state.config.get("API_KEY")
        
        # 3. Return a structured SkillResult
        return SkillResult(
            output={"status": "success"},
            output_text="The operation completed."
        )
```

## 2. Core Library Moves

Several core modules have been moved to better represent the orchestration pipeline. Update your imports as follows:

| Old Import | New Import | Notes |
|---|---|---|
| `core.engine.CoreEngine` | `core.runtime.CoreEngine` | Main entry point moved |
| `core.state.AgentState` | `core.execution.ExecutionState` | Renamed to better match execution boundaries |
| `core.state.Message` | *Deprecated* | Use native memory abstractions or standard dictionaries where applicable |

## 3. Sandboxing & Middlewares

In V2, execution is strictly wrapped in a Middleware pipeline (Trace, Policy, Approval, Timeout). 
* Do not attempt to catch timeout exceptions inside your skill to override them; the kernel handles timeout isolation at a higher level.
* Always ensure your skill's `metadata` property accurately defines its `capabilities` so the `SkillValidator` can properly authorize its execution.

---

# Russian Section / Русская Секция 🇷🇺

# SGR Kernel: Руководство по миграции v1.x -> v2

Архитектура SGR Kernel эволюционировала от монолитного движка (`core.engine`) к событийно-ориентированной архитектуре (`core.runtime`, `Container`, `EventStore`). Хотя обратная совместимость во многом сохранена благодаря адаптерам, обновление ваших `skills/` до нативного V2 API открывает доступ к лучшей телеметрии, хукам жизненного цикла и убирает предупреждения в терминале.

## 1. Миграция сигнатуры `execute`

Самое значительное изменение для разработчиков Скиллов — отказ от сигнатуры `(params, state)` в пользу единого `SkillContext`.

### ❌ Устаревшая сигнатура V1

```python
from core.execution import ExecutionState
from skills.base import BaseSkill

class LegacySkill(BaseSkill):
    # Это всё ещё будет работать благодаря запасному адаптеру, но считается устаревшим
    def execute(self, params: MyInputSchema, state: ExecutionState) -> str:
        api_key = state.config.get("API_KEY")
        return "Успех"
```

### ✅ Современная сигнатура V2

Новый стандарт ожидает асинхронный контекст выполнения, который оборачивает все необходимые данные (конфиг, глобальное состояние, реестр инструментов).

```python
from core.skill_interface import SkillContext, SkillResult
from skills.base import BaseSkill

class ModernSkill(BaseSkill):
    async def execute(self, ctx: SkillContext) -> SkillResult:
        # 1. Извлекаем и валидируем параметры
        params = self.input_schema(**ctx.config)
        
        # 2. Доступ к глобальному состоянию (если строго необходимо)
        api_key = ctx.execution_state.config.get("API_KEY")
        
        # 3. Возвращаем структурированный SkillResult
        return SkillResult(
            output={"status": "success"},
            output_text="Операция завершена."
        )
```

## 2. Перемещение модулей ядра

Несколько базовых модулей были перемещены для лучшего отражения пайплайна оркестрации. Обновите ваши импорты следующим образом:

| Старый импорт | Новый импорт | Примечания |
|---|---|---|
| `core.engine.CoreEngine` | `core.runtime.CoreEngine` | Изменилась основная точка входа |
| `core.state.AgentState` | `core.execution.ExecutionState` | Переименовано для лучшего соответствия границам выполнения |
| `core.state.Message` | *Устарело* | Используйте нативные абстракции памяти или стандартные словари, где применимо |

## 3. Песочницы и Middleware (Связующее ПО)

В V2 выполнение строго обернуто в конвейер Middleware (Трассировка, Политики, Подтверждения, Таймауты).
* Не пытайтесь перехватывать исключения таймаута (timeout exceptions) внутри вашего скилла, чтобы переопределить их; ядро обрабатывает изоляцию таймаутов на более высоком уровне.
* Всегда убеждайтесь, что свойство `metadata` вашего скилла точно определяет его `capabilities` (возможности), чтобы `SkillValidator` мог правильно авторизовать его выполнение.
