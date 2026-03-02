# 📜 Спецификация Swarm Протокола
**Версия протокола:** 1.0

## 1. 🤝 Протокол передачи управления (Handoff Protocol)
SGR Kernel V3 использует многоагентную swarm-архитектуру. Агенты не вызывают друг друга напрямую через функции. Вместо этого они возвращают объект `TransferToAgent` через `TransferSkill`.

Когда агент передает управление, он **обязан** предоставить `context_summary` (сводку контекста), содержащую:
- Первоначальное намерение (intent) пользователя.
- Любые промежуточные открытия или результаты.
- Конкретную причину, по которой управление передается новому агенту.

## 2. 🛡️ Очистка контекста (Bleed Protection)
Чтобы предотвратить инъекции промптов и раздувание контекста, `SwarmEngine` перехватывает передачу управления и **перезаписывает историю сообщений** для входящего агента.
Новый агент получает:
1. Свои собственные `system` инструкции.
2. Одно `user` сообщение, содержащее `[Context from PreviousAgent]: <context_summary>`.

Это гарантирует, что PII и избыточные процессы рассуждений (thought processes) от предыдущих агентов не загрязнят контекстное окно текущего агента.

## 3. 🔄 Защита от зацикливания (Loop Protection)
`SwarmEngine` применяет строгий лимит `max_transfers` (по умолчанию: 5) на каждый ход сессии (session turn). Если агенты будут бесконечно перекидывать запросы друг другу (пинг-понг), ядро перехватит 6-ю передачу и вернет пользователю ошибку эскалации.

## 4. 🗃️ Журнал аудита (WAL)
Каждая успешная передача управления вызывает запись структурированного лога под тегом `transfer_audit`, включая:
- `from_agent`
- `to_agent`
- `context`
Это обеспечивает полную трассируемость решений swarm-агентов в production-средах.

---

## 🇺🇸 English

# 📜 Swarm Protocol Specification
**Protocol Version:** 1.0

## 1. 🤝 Handoff Protocol
The SGR Kernel V3 leverages a multi-agent swarm architecture. Agents do not call each other directly via function calls. Instead, they yield a `TransferToAgent` object via the `TransferSkill`.

When an Agent yields control, it **must** provide a `context_summary` outlining:
- The user's original intent.
- Any intermediate discoveries.
- The specific reason why the control is being transferred to the new Agent.

## 2. 🛡️ Context Sanitization (Bleed Protection)
To prevent prompt injection and context bloat, the `SwarmEngine` intercepts the handoff and **re-writes the message history** for the incoming agent.
The new agent receives:
1. Its own `system` instructions.
2. A single `user` message containing the `[Context from PreviousAgent]: <context_summary>`.

This ensures PII and verbose thought processes from prior agents do not pollute the current agent's context window.

## 3. 🔄 Loop Protection
The `SwarmEngine` enforces a strict `max_transfers` limit (default: 5) per session turn. If agents ping-pong requests back and forth infinitely, the engine will intercept the 6th transfer and return an escalation error to the user.

## 4. 🗃️ Audit Logging (WAL)
Every successful handoff triggers a structured log entry under the `transfer_audit` tag, including:
- `from_agent`
- `to_agent`
- `context`
This allows full traceability of swarm decisions in production environments.
