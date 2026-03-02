# Russian Section / Русская Секция 🇷🇺

# HIPAA Compliance (Защита Медицинских Данных)

Health Insurance Portability and Accountability Act (HIPAA) устанавливает стандарты для защиты чувствительной медицинской информации пациентов. SGR Kernel предоставляет необходимые технические инструменты (Technical Safeguards) для обработки Protected Health Information (PHI).

## Требования к развертыванию (HIPAA Technical Safeguards)

Чтобы использовать SGR Kernel в медицинских целях, необходимо соблюдение следующих архитектурных паттернов:

1. **Изолированный контур (Local AI)**
   Категорически не рекомендуется отправка отрытых PHI данных через публичные LLM API (если у вас не подписан Business Associate Agreement - BAA - с провайдером). Ядро SGR позволяет перевести обработку медицинских агентов исключительно на on-premise модели (через коннектор к vLLM).

2. **End-to-End Шифрование (E2EE)**
   - **В покое (Data at Rest):** Дисковые хранилища (`memory.db` и векторные базы данных) должны быть зашифрованы на уровне файловой системы (AES-256).
   - **В полете (Data in Transit):** Все меж-агентные коммуникации (Swarm Protocol) и вызовы LLM происходят по защищенным каналам (mTLS/HTTPS).

3. **Аудиторский След (Audit Logging)**
   SGR Kernel ведет неизменяемый журнал (Append-only Event Store) всех действий:
   - Кто из пользователей запросил операцию.
   - Какой Агент принял решение.
   - Какой контекст (содержащий PHI) был отправлен модели.
   Эти журналы не подлежат прямой модификации и экспортируются в защищенные SIEM-системы.

4. **Строгий RBAC (Управление Доступом)**
   Только авторизованные сервисы и агенты (имеющие соответствующие `roles/scopes` в метаданных) получают контекст из RAG (Retrieval-Augmented Generation), содержащего медицинские рецепты или диагнозы. Возможна интеграция с корпоративными IAM (Identity and Access Management).

---

## 🇺🇸 English

# HIPAA Compliance (Protected Health Information)

The Health Insurance Portability and Accountability Act (HIPAA) mandates standards for protecting sensitive patient health information. SGR Kernel provides the fundamental Technical Safeguards required for handling Protected Health Information (PHI).

## Deployment Requirements (HIPAA Technical Safeguards)

To utilize SGR Kernel for medical and healthcare use cases, the following architectural patterns must be strictly implemented:

1. **Isolated Perimeter (Local AI)**
   Sending unredacted PHI data through public LLM APIs is strictly prohibited unless a valid Business Associate Agreement (BAA) is established with the provider. SGR Kernel allows administrators to route medical agents' inference exclusively to on-premise models (via the vLLM connector).

2. **End-to-End Encryption (E2EE)**
   - **Data at Rest:** All persistence layers (`memory.db` and vector databases) must be encrypted at the filesystem level (AES-256).
   - **Data in Transit:** All inter-agent communications (Swarm Protocol) and LLM endpoints enforce secure transport (mTLS/HTTPS).

3. **Immutable Audit Logging**
   SGR Kernel maintains an immutable, append-only Event Store tracking all state changes:
   - Which human user requested the operation.
   - Which specific Agent formulated the decision.
   - What exact context (containing PHI) was exposed to the model.
   These logs cannot be mutated directly through the UI and should be securely exported to an enterprise SIEM system.

4. **Strict RBAC (Access Control)**
   Only explicitly authorized services and agents (bearing the correct `roles/scopes` in their manifest) are granted traversal access to RAG databases containing medical records or diagnoses. The system fully supports integration with corporate Identity and Access Management (IAM) platforms.
