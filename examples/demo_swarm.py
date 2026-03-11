"""
SGR Kernel — Минимальный пример Swarm из 2 агентов.

Демонстрирует:
  1. Создание BaseSkill с типизированным input_schema
  2. Создание Agent с набором скиллов
  3. Handoff между агентами через TransferToAgent
  4. Запуск SwarmEngine

Требования:
  pip install -r requirements.txt
  export OPENAI_API_KEY=your-key  # или DEEPSEEK_API_KEY

Запуск:
  python examples/demo_swarm.py
"""

import asyncio
from typing import Any, Optional, Type

from pydantic import BaseModel

from core.agent import Agent, TransferToAgent
from core.swarm import SwarmEngine
from core.types import Capability, SkillMetadata
from skills.base import BaseSkill


# ─── 1. Определяем скиллы ──────────────────────────────

class GreetInput(BaseModel):
    user_name: str


class GreetSkill(BaseSkill[GreetInput]):
    """Приветствует пользователя по имени."""

    @property
    def name(self) -> str:
        return "greet_user"

    @property
    def description(self) -> str:
        return "Приветствует пользователя по имени."

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name=self.name,
            capabilities=[Capability.REASONING],
        )

    @property
    def input_schema(self) -> Type[BaseModel]:
        return GreetInput

    async def execute(self, params: GreetInput, state: Any) -> str:
        return f"Привет, {params.user_name}! Чем могу помочь?"


class TransferToExpertInput(BaseModel):
    reason: str


class TransferToExpertSkill(BaseSkill[TransferToExpertInput]):
    """Передаёт управление агенту-эксперту."""

    def __init__(self, expert_agent: Agent):
        self._expert = expert_agent

    @property
    def name(self) -> str:
        return "transfer_to_expert"

    @property
    def description(self) -> str:
        return "Передать задачу агенту-эксперту для глубокого анализа."

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name=self.name,
            capabilities=[Capability.REASONING],
        )

    @property
    def input_schema(self) -> Type[BaseModel]:
        return TransferToExpertInput

    async def execute(self, params: TransferToExpertInput, state: Any) -> TransferToAgent:
        return TransferToAgent(
            agent=self._expert,
            context_message=params.reason,
        )


# ─── 2. Собираем Swarm ─────────────────────────────────

def build_swarm():
    # Агент-эксперт
    expert = Agent(
        name="ExpertAgent",
        instructions="Ты — эксперт-аналитик. Отвечай подробно и структурированно.",
        skills=[GreetSkill()],
    )

    # Router-агент
    router = Agent(
        name="RouterAgent",
        instructions=(
            "Ты — маршрутизатор запросов. "
            "Если вопрос требует детального анализа — передай его ExpertAgent. "
            "Иначе ответь сам."
        ),
        skills=[
            GreetSkill(),
            TransferToExpertSkill(expert),
        ],
    )

    return router, expert


# ─── 3. Запуск ──────────────────────────────────────────

async def main():
    router, expert = build_swarm()

    engine = SwarmEngine(
        llm_config={"model": "deepseek-chat"},
    )

    messages = [{"role": "user", "content": "Проанализируй архитектуру микросервисов"}]

    response = await engine.execute(
        starting_agent=router,
        messages=messages,
        max_turns=10,
    )

    print("\n═══ Результат ═══")
    print(f"Финальный агент: {response.agent.name}")
    for msg in response.messages:
        role = msg.get("role", "?")
        content = msg.get("content", "")
        if content:
            print(f"[{role}] {content[:200]}")


if __name__ == "__main__":
    asyncio.run(main())
