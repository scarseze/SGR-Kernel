# Russian Section / Русская Секция 🇷🇺

# GDPR Compliance (Европейский Регламент по Защите Данных)

Архитектура SGR Kernel изначально проектировалась с учетом строгих требований к безопасности персональных данных (PII) и соблюдению регламентов, таких как **GDPR / EU DPA**. Развертывание системы в Enterprise-окружении позволяет соответствовать всем пунктам законодательства.

## Ключевые механизмы защиты

1. **Минимизация данных (Data Minimization)**
   Служба памяти агента (`UIMemory` и `EventStore`) поддерживает автоматическое устаревание контекста (TTL) и очистку `swarm_chat_history.db` по расписанию. Данные хранятся ровно столько, сколько нужно для выполнения сеанса.

2. **Маскирование и Анонимизация PII (Data Masking)**
   Встроенный `SecurityGuardian` умеет перехватывать конфиденциальные данные перед их отправкой сторонним LLM-провайдерам.
   - Имена, email-адреса, телефоны и номера банковских карт могут автоматически заменяться на псевдонимы (например, `[REDACTED_EMAIL]`).
   - Для работы с немодифицированными данными рекомендуется использование локальных LLM (через vLLM или Ollama) в защищенном контуре.

3. **Право на Забвение (Right to be Forgotten)**
   Архитектура событийного хранилища (Event Store) позволяет извлекать все данные, связанные с конкретным `user_id`, и производить каскадное криптографическое удаление (Crypto-shredding). Вместо физического удаления всех блоков (что ломает аудиторский след), ядро удаляет ключи шифрования, делая контент недоступным.

4. **Локализация обработки**
   При конфигурации ядра администратор может привязать конкретных агентов (или навыки) к локально развернутым моделям, гарантируя, что чувствительная часть данных пользователей ЕС физически не покинет дата-центр.

**Пример конфигурации (`configs/compliance/gdpr_example.yaml`):**
```yaml
compliance:
  standard: "gdpr"
  pii_redaction: true
  allowed_llm_regions: ["eu-west-1", "eu-central-1"]
  data_retention_days: 30
```

---

## 🇺🇸 English

# GDPR Compliance (General Data Protection Regulation)

The SGR Kernel architecture was designed from the ground up with strict Personally Identifiable Information (PII) security and compliance frameworks like **GDPR** in mind. Deploying the system in an Enterprise environment ensures full adherence to legal requirements.

## Key Protection Mechanisms

1. **Data Minimization**
   The agent memory service (`UIMemory` and `EventStore`) supports automated context obsolescence (TTL) and scheduled purging of `swarm_chat_history.db`. Data is stored exactly as long as needed for the active session.

2. **PII Masking and Anonymization**
   The built-in `SecurityGuardian` intercepts confidential data before it leaves your network to third-party LLM providers.
   - Names, email addresses, phone numbers, and credit card patterns can be automatically pseudonymized (e.g., `[REDACTED_EMAIL]`).
   - For processing unredacted data, it is strongly advised to deploy local LLMs (via vLLM or Ollama) within a secure perimeter.

3. **Right to be Forgotten (Erasure)**
   The Event Store architecture allows system administrators to query all data associated with a specific `user_id` and perform cascaded Crypto-shredding. Instead of physically scrubbing all blocks (which corrupts the audit trail), the kernel securely deletes the encryption keys, rendering the personal content permanently unreadable.

4. **Processing Localization**
   During kernel configuration, administrators can pin specific agents or individual skills to locally hosted models, guaranteeing that sensitive EU user data never physically leaves the designated datacenter.

**Configuration Example (`configs/compliance/gdpr_example.yaml`):**
```yaml
compliance:
  standard: "gdpr"
  pii_redaction: true
  allowed_llm_regions: ["eu-west-1", "eu-central-1"]
  data_retention_days: 30
```
