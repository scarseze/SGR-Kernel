# SGR Kernel: L8 Distinguished System Invariants / Ядро SGR: Инварианты системы уровня L8 Distinguished

---

Этот документ формализует строгие инварианты, границы эксплуатации и математические гарантии архитектуры SGR Kernel. Он восполняет пробел между эмпирической устойчивостью и формально доказуемой корректностью в условиях агрессивных сбоев.

### 🚦 G0: Модель сбоев системы
Прежде чем определять инварианты, мы четко заявляем границы нашей области сбоев:

* **Сбои типа Crash-Stop:** Узлы выходят из строя путем полной остановки. Мы не допускаем «византийских» воркеров (вредоносных или произвольно изменяющих состояние).
* **Предположения об оборудовании:** Подсистема хранения (БД, S3) обеспечивает долговечное, упорядоченное по записи хранение, но может иметь неопределенные задержки.
* **Конечное восстановление сети:** Разделение сети может происходить, но в конечном итоге будет устранено, позволяя компонентам восстановить связь в ограниченные сроки.
* **Асинхронность:** Мы работаем в асинхронной системе. Логика, зависящая от времени (аренда, таймауты), абсолютно полагается на центральный монотонный источник истины (БД `CURRENT_TIMESTAMP`), рассматривая локальные часы Python как ненадежные.

---

### 📉 G1: Стабильность очереди (λ < μ) под обратным давлением
Система обеспечивает ограниченную глубину очередей для поддержания математического инварианта стабильности очереди, где скорость поступления (λ) должна оставаться строго меньше скорости обслуживания (μ).

* **Инвариант:** Система будет проактивно сбрасывать избыточную нагрузку до того, как локальные очереди или пулы памяти будут исчерпаны.
* **Обеспечение:** Достигается через многомерный Admission Control (см. Приложение).

---

### 🔄 G2: Гарантия конечного прогресса (Предотвращение Livelock)
При изоляции `SERIALIZABLE` в БД уровня данных частота прерывания транзакций может резко возрастать при высокой конкуренции (конфликты CAS).

* **Угроза Livelock:** «Горячий» раздел или непрерывный приток задач могут теоретически помешать успеху любой конкретной задачи, что означает стремление конкуренции $C$ к $\infty$.
* **Гарантия инварианта:** Конечный прогресс обеспечивается при ограниченной конкуренции, контролируемой через допуск (admission control) по конфликтующим ключам.
* **Обеспечение:**
  1. **Admission Control на уровне разделов:** Система явно ограничивает одновременное получение аренды на одном и том же «горячем» разделе, структурно ограничивая конкуренцию $C$.
  2. **Максимальный бюджет ретраев:** Воркеры соблюдают строгий бюджет на ошибки изоляции БД, используя экспоненциальный бэк-офф с полным джиттером.
  3. **Резервный путь (Эскалация приоритета):** Если задача исчерпывает бюджет ретраев, она освобождает аренду и повторно вставляется в слой очередей с повышенным приоритетом (справедливость порядка очереди), позволяя «горячему» разделу остыть.

---

### 🔌 G3: Декомпозиция уровня данных (Независимость уровня выполнения)
Домены сбоев между Control Plane (БД/Оркестратор) и Execution Plane (воркеры) строго разделены.

* **Инвариант:** Уровень выполнения не зависит от БД во время работы. Независимость выполнения достигается ценой требования глобально идемпотентных побочных эффектов.
* **Объяснение:** Сбои БД не вызовут мгновенного отказа или краха выполняющихся задач. Однако при восстановлении БД задачи могут завершить вычисления, но не суметь записать состояние `COMPLETED`, что приведет к их последующему повторному выполнению через `BackgroundReconciler`.
* **Ограничение границ:** Поскольку дублирование выполнения ограничено, но возможно, ВСЕ побочные эффекты, инициируемые воркером (например, записи в хранилище, вызовы внешних API, биллинг, обратные вызовы), должны быть по своей природе **идемпотентными** ИЛИ явно защищены **внешними ключами идемпотентности**.

---

### 📦 G4: Протокол атомарного хранения S3 (Видимость «ровно один раз»)
Мы отвергаем идею атомарного `rename` в объектном хранилище S3 (так как `rename` в S3 — это фундаментально ошибочная операция `COPY` + `DELETE`, допускающая частичную видимость).

* **Инвариант:** Данные, опубликованные в S3, должны быть атомарно видимы всем потребителям без промежуточных или дублирующихся состояний. Сохраняется только последняя зафиксированная версия.
* **Обеспечение:** Мы применяем **Шаблон маркера коммита** с версионными объектами и очисткой мусора:
  * Воркеры записывают артефакты по уникальному версионному префиксному пути: `/job_id/v_<attempt_id>/data.bin`
  * **Валидация:** После полной записи полезной нагрузки атомарно записывается маркер коммита размером ноль байт `/job_id/_SUCCESS`. Этот маркер содержит контрольную сумму для проверки после записи и указатель на путь версии.
  * **Идемпотентность:** Потребители строго блокируются на маркере `_SUCCESS` и проверяют контрольную сумму, гарантируя идемпотентность и защищая от повреждения данных при частичном копировании.
  * **Очистка мусора (GC):** Фоновый процесс асинхронно собирает устаревшие директории с префиксом `v_*`. Безопасно сохраняется только версия, на которую указывает маркер `_SUCCESS`.

---
---

## 🇺🇸 English

This document formalizes the rigorous invariants, operational boundaries, and mathematical guarantees of the SGR Kernel architecture. It bridges the gap between empirical resilience and formally provable correctness under adversarial conditions.

### 🚦 G0: System Failure Model
Before defining system invariants, we explicitly state the boundaries of our failure domain:

*   **Crash-Stop Failures:** Nodes fail by halting completely. We do not tolerate Byzantine (malicious or arbitrary state mutating) workers.
*   **Hardware Assumptions:** Storage subsystem (DB, S3) provides durable, write-ordered persistence but can experience indeterminate latency.
*   **Eventual Network Recovery:** Network partitions may occur but will eventually heal, allowing components to reconnect boundedly.
*   **Asynchrony:** We operate in an asynchronous system. Time-dependent logic (leases, timeouts) relies absolutely on a central monotonic source of truth (DB `CURRENT_TIMESTAMP`), treating local Python clocks as untrusted.

### 📉 G1: Queue Stability ($\lambda < \mu$) under Backpressure
The system enforces bounded queue depths to maintain the mathematical invariant of queue stability, where the arrival rate ($\lambda$) must remain strictly less than the service rate ($\mu$).

*   **Invariant:** The system will shed excess load proactively before local queues or memory pools are exhausted.
*   **Enforcement:** Achieved via multi-dimensional Admission Control (see Annex).

### 🔄 G2: Eventual Progress Guarantee (Livelock Prevention)
Under `SERIALIZABLE` isolation in the Data Plane DB, transaction abort rates can spike under high contention (CAS conflicts). 

*   **The Livelock Threat:** A hot partition or continuous inflow could theoretically prevent a single job from ever succeeding, meaning contention $C$ goes to $\infty$.
*   **Invariant Guarantee:** Eventual progress holds under bounded contention enforced via admission control on conflicting keys.
*   **Enforcement:**
    1.  **Partition-Level Admission Control:** The system explicitly throttles concurrent lease acquisitions on the same hot partition, bounding contention $C$ structurally.
    2.  **Max Retry Budget:** Workers enforce a strict budget on DB isolation failures using exponential backoff with full jitter.
    3.  **Fallback Path (Priority Escalation):** If a job exhausts its retry budget, it yields its lease and reinserts itself into the queuing layer with escalated priority (queue ordering fairness), allowing the hot partition to cool down.

### 🔌 G3: Data-Plane Decoupling (Execution Plane Independence)
Failure domains between the Control Plane (DB/Orchestrator) and the Execution Plane (Workers) are strictly decoupled.

*   **Invariant:** Execution plane is DB-independent during runtime. Execution independence is achieved at the cost of requiring globally idempotent side-effects.
*   **Explanation:** DB outages will not cause running executions to instantly fail or crash. However, during a database recovery, jobs may complete their computation but fail to write the `COMPLETED` state, leading to later re-execution by the `BackgroundReconciler`. 
*   **Boundary Constraint:** Because execution duplication is bounded but possible, ALL side-effects triggered by a worker (e.g., storage writes, external API calls, billing, callbacks) must be inherently **idempotent** OR explicitly guarded by **external idempotency keys**.

### 📦 G4: Atomic S3 Storage Protocol (Exactly-Once Visibility)
We reject the premise of atomic `rename` on S3 object storage (as S3 `rename` is a fundamentally flawed `COPY` + `DELETE` operation exposing partial visibility).

*   **Invariant:** Data published to S3 must be atomically visible to all consumers without intermediate or duplicated states. Only the latest committed version is retained.
*   **Enforcement:** We enforce a **Commit Marker Pattern** with Versioned Objects and Garbage Collection:
    *   Workers write artifacts to a uniquely versioned prefix path: `/job_id/v_<attempt_id>/data.bin`
    *   **Validation:** After a full payload write, a zero-byte commit marker `/job_id/_SUCCESS` is written atomically. This marker crucially contains a read-after-write **checksum** and a pointer to the versioned path.
    *   **Idempotency:** Downstream consumers strictly block on the `_SUCCESS` marker and validate the checksum, guaranteeing idempotency and shielding against partial `COPY` corruption.
    *   **Garbage Collection (GC):** A background sweeper asynchronously collects stale `v_*` prefix directories. Only the version pointed to by the `_SUCCESS` marker is safely retained.
