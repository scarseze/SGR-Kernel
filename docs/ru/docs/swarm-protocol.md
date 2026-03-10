# Swarm Protocol Specification
**Protocol Version:** 1.0

## 1. Handoff Protocol
The SGR Kernel V3 leverages an enterprise multi-agent swarm architecture. Agents do not call each other directly via function calls. Instead, they yield a `TransferToAgent` object via the `TransferSkill`.

When an Agent yields control, it **must** provide a `context_summary` outlining:
- The user's original intent.
- Any intermediate discoveries.
- The specific reason why the control is being transferred to the new Agent.

## 2. Context Sanitization (Bleed Protection)
To prevent prompt injection and context bloat, the `SwarmEngine` intercepts the handoff and **re-writes the message history** for the incoming agent.
The new agent receives:
1. Its own `system` instructions.
2. A single `user` message containing the `[Context from PreviousAgent]: <context_summary>`.

This ensures PII and verbose thought processes from prior agents do not pollute the current agent's context window.

## 3. Loop Protection
The `SwarmEngine` enforces a strict `max_transfers` limit (default: 5) per session turn. If agents ping-pong requests back and forth infinitely, the engine will intercept the 6th transfer and return an escalation error to the user.

## 4. Audit Logging (WAL)
Every successful handoff triggers a structured log entry under the `transfer_audit` tag, including:
- `from_agent`
- `to_agent`
- `context`
This allows full traceability of swarm decisions in production environments.

---

# Спецификация протокола Swarm (Swarm Protocol Specification)
**Версия протокола:** 1.0

## 1. Протокол передачи управления (Handoff Protocol)
SGR Kernel V3 использует корпоративную мультиагентную Swarm-архитектуру. Агенты не вызывают друг друга напрямую через функции. Вместо этого они возвращают объект `TransferToAgent` через `TransferSkill`.

При передаче управления Агент **обязан** предоставить `context_summary`, содержащий:
- Исходное намерение пользователя.
- Промежуточные открытия и результаты.
- Конкретную причину передачи управления новому Агенту.

## 2. Санитизация контекста (Bleed Protection)
Для предотвращения инъекций промптов и раздувания контекста, `SwarmEngine` перехватывает передачу и **перезаписывает историю сообщений** для входящего агента.
Новый агент получает:
1. Свои собственные инструкции `system`.
2. Одно сообщение `user` с `[Context from PreviousAgent]: <context_summary>`.

Это гарантирует, что PII и многословные внутренние рассуждения предыдущих агентов не загрязняют контекстное окно текущего агента.

## 3. Защита от зацикливания (Loop Protection)
`SwarmEngine` устанавливает строгий лимит `max_transfers` (по умолчанию: 5) на сессионный ход. Если агенты бесконечно перебрасывают запросы друг другу, движок перехватит 6-ю передачу и вернёт пользователю ошибку эскалации.

## 4. Журнал аудита (WAL)
Каждая успешная передача управления создаёт структурированную запись журнала с тегом `transfer_audit`, включающую:
- `from_agent` — агент-источник
- `to_agent` — агент-получатель
- `context` — переданный контекст

Это обеспечивает полную прослеживаемость решений роя в production-среде.
