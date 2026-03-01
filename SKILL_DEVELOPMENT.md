# SGR Skill Development Guide / Руководство по разработке скиллов SGR

> Learn how to build new capabilities for the SGR Swarm. / Узнайте, как создавать новые возможности для SGR Swarm.

---

## 🇷🇺 Русский (Russian)

### Философия: Почему SGR?
В отличие от стандартных агентов, следующих текстовым инструкциям, SGR-агент следует **структурам данных** (Schema-Guided). Это гарантирует предсказуемость и интеграцию в сложные системы.

### Анатомия скилла
Каждый скилл в `skills/` состоит из:
1.  **`schema.py`**: Pydantic-схема (входные параметры).
2.  **`handler.py`**: Логика выполнения на Python.
3.  **`__init__.py`**: Регистрация скилла.

### Пример создания
```python
from pydantic import BaseModel, Field
from core.skill_interface import SkillContext, SkillResult
from skills.base import BaseSkill

class MyInput(BaseModel):
    query: str = Field(description="Поисковый запрос")

class MySkill(BaseSkill):
    name = "my_skill"
    description = "Демонстрационный скилл"
    async def execute(self, ctx: SkillContext) -> SkillResult:
        query = ctx.params.get("query", "")
        return SkillResult(output_text=f"Результат для: {query}")
```

---

## 🇺🇸 English

### Philosophy: Why SGR?
Unlike standard agents that follow text instructions, SGR agents follow **data structures** (Schema-Guided). This ensures predictability and seamless integration into complex pipelines.

### Anatomy of a Skill
Every skill in `skills/` consists of:
1.  **`schema.py`**: Pydantic schema (input parameters).
2.  **`handler.py`**: Execution logic in Python.
3.  **`__init__.py`**: Skill registration.

### Step-by-Step
```python
from pydantic import BaseModel, Field
from core.skill_interface import SkillContext, SkillResult
from skills.base import BaseSkill

class MyInput(BaseModel):
    query: str = Field(description="Search query")

class MySkill(BaseSkill):
    name = "my_skill"
    description = "Demo skill"
    async def execute(self, ctx: SkillContext) -> SkillResult:
        query = ctx.params.get("query", "")
        return SkillResult(output_text=f"Result for: {query}")
```
