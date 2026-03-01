# Agent Kernel Specification v3.0 / Спецификация Ядра Агента v3.0

> Formal execution protocol for `sgr_kernel` SwarmEngine runtime. / Формальный протокол выполнения для рантайма SwarmEngine.

---

## 🇷🇺 Русский (Russian)

### 1. Распределение ответственности
**Ядро (SwarmEngine) отвечает за:**
- Оркестрацию роя (Swarm) и передачу контекста (Transfer) между агентами.
- Работу Middleware, контроль лимита ходов (max_turns) и таймауты.
- Валидацию безопасности (ввод, параметры скиллов, вывод агента).
- Хранение истории диалога и консистентность состояния роя.

### 2. Жизненный цикл запроса
1. Валидация ввода пользователя (Security).
2. Инициализация активного агента (чаще всего Router).
3. Исполнение цикла Swarm:
   - Вызов LLM текущего агента.
   - Выполнение инструментов (Skills) или передача управления другому агенту (Transfer).
   - Запись в историю.
4. Финализация и возврат ответа.

### 3. Гарантии безопасности
- Передача управления (Transfer) между агентами логгируется и проверяется.
- Скиллы не запускаются без прохождения проверки прав (ACL).
- Вывод любого агента санируется перед показом пользователю.
- Лимит ходов (max_turns) предотвращает бесконечные циклы переходов.

---

## 🇺🇸 English

### 1. Responsibility Boundary
**Kernel (SwarmEngine) owns:**
- Swarm orchestration and context transfer between specialized agents.
- Middleware enforcement, turn limit control (max_turns), and timeouts.
- Security validation (input, tool params, agent output).
- Conversation history persistence and swarm state consistency.

### 2. Request Lifecycle
1. User input validation (Security).
2. Active agent initialization (defaults to Router).
3. Swarm loop execution:
   - LLM call for the active agent.
   - Tool execution (Skills) or handoff to another agent (Transfer).
   - History logging.
4. Finalization and response return.

### 3. Safety Invariants
- Handoffs (Transfer) between agents are traced and validated.
- No Skill runs without passing ACL/Policy checks.
- Output from any agent is sanitized before reaching the user.
- Turn limits (max_turns) prevent infinite redirection loops.

---

## Technical Details / Технические детали

### Swarm Pipeline / Очередь Swarm
| Phase / Фаза | Mechanism / Механизм |
| :--- | :--- |
| `Turn Control` | max_turns boundary (default: 10) |
| `Transfer` | Pure conversational handoff via History |

### Security Checks / Проверки безопасности
| Policy / Политика | Trigger / Триггер |
| :--- | :--- |
| `Input Validation` | Every user message |
| `Skill ACL` | Before every Tool call |
| `Output Sanitization` | Final agent response |
