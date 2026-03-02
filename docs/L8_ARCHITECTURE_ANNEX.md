# SGR Kernel: L8 Architecture Annex & Tradeoffs / Ядро SGR: Приложение по архитектуре L8 и компромиссам

---

В этом приложении описаны явные архитектурные ограничения, глубоко проработанные компромиссы и механизмы изоляции, используемые для создания системы с надежностью уровня Top 1% в условиях агрессивных сбоев и конкуренции за ресурсы.

### 1. 🔄 Компромисс SERIALIZABLE и конкуренция
**Решение:** Мы вводим обязательную изоляцию транзакций `SERIALIZABLE` для обновлений внутреннего состояния БД (Compare-And-Swap через `lease_version`), чтобы предотвратить состояние гонки между Reconciler и воркерами.

* **Осознанный выбор:** Мы намеренно жертвуем пропускной способностью ради структурной целостности, допуская частоту прерывания транзакций до 15% при высокой нагрузке, вместо риска дублирующегося или поврежденного выполнения.
* **Прогресс под давлением (Смягчение Livelock):** Поскольку постоянные конфликты CAS теоретически могут привести к голоданию воркера, мы внедряем бюджеты на ретраи с джиттером в сочетании с механизмом резервной повторной вставки для обеспечения справедливого получения аренды. Мы формально заявляем: *Система гарантирует конечный прогресс при ограниченной конкуренции C.*

### 2. 🚦 Многомерный Admission Control (DRF)
**Решение:** Простые корзины токенов на тенанта (`tenant_inflight`) успешно останавливают глобальные каскадные сбои 503, но они не учитывают неоднородность ресурсов.

* **Вектор конкуренции:** Если Тенант А отправляет небольшое количество задач, сильно нагружающих GPU, базовое ограничение частоты все равно позволит Тенанту А насытить общий пул оборудования, негативно влияя на задержку легковесных задач Тенанта Б, ориентированных на CPU.
* **Эволюция к многомерным квотам:** Чтобы предотвратить конкуренцию за общую инфраструктуру, Admission Control использует Dominant Resource Fairness (DRF). Квоты и токены вычисляются на основе векторов ресурсов (CPU, GPU VRAM, IO), гарантируя, что ни один тенант не сможет монополизировать конкретный дефицитный ресурс, даже если его абсолютная частота запросов низка.
* **Политика предотвращения голодания:** DRF сам по себе не может предотвратить бесконечное голодание низкоприоритетной задачи. Поэтому система обеспечивает **взвешенную справедливость с гарантированным минимумом** (floor allocation) и **эскалацию приоритета на основе времени ожидания**, гарантируя, что задержка выполнения остается строго ограниченной даже для тенантов с самым низким приоритетом.

### 3. ⏱️ SLO по задержкам и моделирование усиления задержки
**Решение:** Мы декларируем декомпозированный SLO по задержкам ($t_{queue} + t_{exec} + t_{storage}$), поддерживая задержки на уровне P95 в пределах заданных порогов.

* **Угроза усиления задержки:** Мы явно отвергаем наивное предположение о том, что общая задержка хвоста (P95) — это просто сумма независимых задержек компонентов ($T_{total} = \sum P95_{components}$). Мы признаем, что задержки сильно коррелируют (например, ретраи API хранилища напрямую увеличивают время выполнения, что повышает конкуренцию за соединения с БД, замедляя время в очереди).
* **Изоляция и соблюдение SLO:** Мы моделируем эту корреляцию и обеспечиваем строгую изоляцию SLO на каждом этапе через ограниченные лимиты выполнения и независимые circuit breakers, чтобы предотвратить каскадное усиление задержек.
* **Автоматический цикл контроля:** Любое нарушение SLO в реальном времени вызывает автоматическое действие: система проактивно *масштабирует ресурсы*, *сбрасывает избыточную нагрузку* или *деградирует некритичные функции*, чтобы не допустить накопления задержек на уровне P99.

### 4. 🌍 Мульти-региональная семантика и домены сбоев
**Решение:**

* **Control Plane:** Работает в режиме отказоустойчивого DNS-переключения (Active/Passive).
* **Data Plane:** Воркеры работают без сохранения состояния (stateless); задачи воспроизводимы в разных регионах.
* **Зависимость от БД:** Критически важно, что уровень выполнения отделен от доступности БД во время активной фазы вычислений. Хотя простой БД предотвратит фиксацию состояния (вызывая повторное выполнение через reconciler), он не приведет к краху физического узла выполнения задачи.

### 5. 📦 Идемпотентное хранилище: Шаблон маркера коммита
Мы явно избегаем псевдо-атомарных шаблонов `RENAME` в объектном хранилище (`S3_COPY` + `S3_DELETE`).

* Вместо перемещения временного файла `.tmp` в финальный путь, SGR Kernel использует структуру маркеров коммита.
* Только наличие атомарно загруженного файла-указателя `_SUCCESS` подтверждает атомарную готовность выходных данных задачи.

---
---

## 🇺🇸 English

This annex describes the explicit architectural constraints, deeply considered tradeoffs, and isolation mechanisms employed to achieve a Top 1% predictable system under adversarial failure conditions and noisy-neighbor contention.

### 1. 🔄 The SERIALIZABLE Tradeoff & Contention
**Decision:** We mandate `SERIALIZABLE` transaction isolation for internal DB state updates (Compare-And-Swap via `lease_version`) to prevent Reconciler vs Worker race conditions.

*   **Conscious Choice:** We deliberately trade concurrency throughput for structural integrity, accepting a transaction abort rate of up to 15% under high load rather than risking duplicate/corrupted executions.
*   **Progress Under Contention (Livelock Mitigation):** Since constant CAS conflicts could theoretically starve a worker, we implement max retry budgets with jitter, paired with a fallback reinsertion mechanism to ensure fair lease acquisition. We formally state: *The system guarantees eventual progress under bounded contention C.*

### 2. 🚦 Multi-Dimensional Admission Control (DRF)
**Decision:** Simple per-tenant token buckets (`tenant_inflight`) successfully stop global 503 cascades, but they fail to account for resource heterogeneity. 

*   **Contention Vector:** If Tenant A submits a small number of massively GPU-heavy jobs, basic rate limiting still allows Tenant A to saturate the shared hardware pool, negatively impacting the latency of Tenant B's lightweight CPU-bound jobs.
*   **Evolution to Multi-Dimensional Quotas:** To prevent shared infrastructure contention, Admission Control employs Dominant Resource Fairness (DRF). Quotas and tokens are computed based on resource vectors (CPU, GPU VRAM, IO), ensuring no single tenant can monopolize a specific bottleneck resource even if their absolute request rate is low.
*   **Starvation Policy:** DRF on its own cannot prevent a low-priority job from starving indefinitely. Therefore, the system enforces **weighted fairness with floor allocation** (min-guarantees) and **age-based priority escalation**, ensuring that execution latency remains strictly bound even for the lowest priority tenants.

### 3. ⏱️ Latency SLO & Tail Amplification Modeling
**Decision:** We declare a decomposed Latency SLO ($t_{queue} + t_{exec} + t_{storage}$), maintaining P95 latencies under predefined thresholds.

*   **The Amplification Threat:** We explicitly reject the naive assumption that the total tail latency is the sum of independent component tail latencies ($T_{total} = \sum P95_{components}$). We recognize that delays are highly correlated (e.g., storage API retries directly bloat execution times, which increases active DB connection contention, dragging down queue times).
*   **SLO Isolation & Enforcement:** We model this tail correlation and enforce strict per-stage SLO isolation via bounded execution limits and independent circuit breakers to prevent tail amplification from cascading across boundaries. 
*   **Automated Enforcement Loop:** Any real-time SLO violation triggers an automatic action: the system will proactively *scale out resources*, *shed excess load*, or *degrade non-critical features* rather than allowing P99 latencies to compound.

### 4. 🌍 Multi-Region Semantics & Failure Domains
**Decision:** 

*   **Control Plane:** Operates in an Active/Passive DNS failover arrangement.
*   **Data Plane:** Workers run statelessly; tasks are replayable across regions. 
*   **DB Dependency:** Crucially, the execution plane is decoupled from DB availability during the active computation phase. While DB downtime will prevent state commits (triggering eventual reconciler-driven re-execution), it will not crash the physical compute execution node in flight.

### 5. 📦 Idempotent Storage: The Commit Marker Pattern
We explicitly avoid pseudo-atomic `RENAME` patterns on Object Storage (`S3_COPY` + `S3_DELETE`).

*   Instead of moving a `.tmp` file to a final path, SGR Kernel employs a precise Commit Marker structure. 
*   Only the presence of an atomically uploaded `_SUCCESS` pointer file confirms the atomic maturity of a job's output data.
