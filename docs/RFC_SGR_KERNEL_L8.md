# RFC: SGR Kernel — Deterministic Execution Layer with Formal Guarantees / Ядро SGR — Слой детерминированного выполнения с формальными гарантиями

---

## [RU] РУССКАЯ ВЕРСИЯ

### Статус
Черновик (Кандидат на уровень L8 — Distinguished Systems Tier)

### Авторы
Инженерная команда SGR Kernel

### Рецензенты
Principal / Staff Инженеры распределенных систем

---

### 1. Аннотация
SGR Kernel — это слой детерминированного выполнения, предназначенный для обеспечения **доказуемых гарантии корректности** выполнения распределенных задач в условиях частичных сбоев, конкуренции и сетевой асинхронности.

В отличие от традиционных систем оркестрации (например, Kubernetes), которые гарантируют планирование на уровне инфраструктуры, SGR Kernel гарантирует:
* **Эксклюзивность выполнения** (Execution exclusivity)
* **Доставку «хотя бы один раз» с ограниченным дублированием** (At-least-once delivery)
* **Атомарную видимость побочных эффектов** (Atomic visibility)
* **Гарантированный прогресс при ограниченной конкуренции** (Eventual progress)

Система формализует корректность через явные инварианты, изоляцию доменов сбоев и идемпотентность на уровне хранилища.

---

### 2. Мотивация
Современным распределенным системам не хватает **надежной границы выполнения**.

Существующие системы:
* планируют вычисления (Kubernetes)
* транспортируют сообщения (Apache Kafka)
* хранят данные (Google Spanner)

Но ни одна из них не гарантирует:
> «Задача выполняется корректно ровно один раз в присутствии ретраев, сбоев и частичных коммитов».

Этот пробел приводит к:
* дублирующимся побочным эффектам
* несогласованным переходам состояний
* неограниченному усилению ретраев
* неопределенному поведению при сбоях

SGR Kernel решает эту проблему, выступая в качестве **слоя корректности** между намерением (запуском задачи) и выполнением.

---

### 3. Не-Цели
* Не является фреймворком для агентов
* Не является движком воркфлоу
* Не является планировщиком общего назначения
* Не является платформой для разработчиков или интерфейсом пользователя

SGR Kernel — это строго:
> **Минимальное ядро выполнения с формально определенными гарантиями**

---

### 4. Модель системы

#### 4.1 Компоненты
* **Control Plane (Уровень управления)**
  * API Оркестратора
  * Основная БД (единый источник истины)
* **Execution Plane (Уровень выполнения)**
  * Stateless-воркеры
  * Изолированные среды выполнения
* **Queue Layer (Уровень очередей)**
  * Эфемерный транспорт (непостоянный)
* **Storage Layer (Уровень хранилища)**
  * Объектное хранилище (идемпотентная запись)

---

#### 4.2 Конечный автомат (State Machine)
Жизненный цикл задачи:
```
CREATED → QUEUED → RUNNING → COMPLETED | FAILED
```
Переходы обеспечиваются через:
* Compare-And-Swap (CAS)
* Владение арендой (Lease ownership)
* Монотонность версий

---

#### 4.3 Источник истины
* **База данных = единственный источник истины**
* Очередь = только оптимизация
* Хранилище = приемник побочных эффектов

---

### 5. Формальные инварианты

#### I1: Эксклюзивность выполнения
Максимум один воркер может удерживать валидную аренду (lease) для задачи.
**Обеспечение:**
* CAS по `lease_version`
* Изоляция SERIALIZABLE

---

#### I2: Доставка «хотя бы один раз»
Каждая задача в конечном итоге будет выполнена.
**Обеспечение:**
* Постоянное состояние `CREATED`
* Повторная постановка в очередь через Reconciler

---

#### I3: Ограниченное дублирование
Количество попыток дублирующего выполнения на один цикл аренды ≤ 1.
**Обеспечение:**
* Истечение срока аренды + запас прочности
* Отклонение устаревших воркеров через CAS

---

#### I4: Атомарная видимость
Частичные результаты не должны быть видны извне.
**Обеспечение:**
* Протокол маркеров коммита (Commit marker) в объектном хранилище

---

#### I5: Гарантированный прогресс
Все задачи завершаются при ограниченной конкуренции.
**Обеспечение:**
* Admission control (контроль допуска)
* Бюджеты на ретраи + джиттер
* Эскалация приоритетов

---

### 6. Модель сбоев

#### Предположения
* Только сбои типа crash-stop (остановка узла)
* Отсутствие «византийских» (вредоносных) воркеров
* Конечное восстановление сети
* Асинхронная система

Авторитет времени:
* БД `CURRENT_TIMESTAMP` является каноническим
* Локальные часы не считаются надежными

---

### 7. Сценарии сбоев (доказательные наброски)

#### Сценарий A: Сбой воркера во время выполнения
* Аренда истекает
* Reconciler повторно ставит задачу в очередь
**Гарантия:** Выполнение не потеряно, дублирование ограничено.

#### Сценарий B: Дублирующиеся воркеры
* Два воркера пытаются выполнить одну и ту же задачу
**Результат:** Только один CAS проходит успешно.
**Гарантия:** Отсутствие конкурентного выполнения.

#### Сценарий C: Воркер-зомби
* Воркер просыпается после потери аренды
**Результат:** CAS на коммите терпит неудачу.
**Гарантия:** Отсутствие устаревших записей.

#### Сценарий D: Потеря очереди (сбой Redis)
* Состояние очереди исчезает
**Результат:** Reconciler восстанавливает данные из БД.
**Гарантия:** Потери задач нет.

#### Сценарий E: Сбой БД во время коммита
* Воркер завершил работу, но не может сохранить состояние
**Результат:** Задача выполняется повторно.
**Гарантия:** Корректность сохраняется благодаря идемпотентности.

---

### 8. Контракт хранилища
SGR Kernel требует:
> **Все побочные эффекты должны быть идемпотентными**

#### Протокол коммита
1. Запись по версионному пути:
   ```
   /job_id/v_<attempt_id>/data
   ```
2. Проверка контрольной суммы (checksum)
3. Запись маркера коммита:
   ```
   /job_id/_SUCCESS
   ```
Потребители: читают данные только после появления `_SUCCESS`.

---

### 9. Стабильность очередей и Admission Control
Пусть:
* λ = частота поступления задач
* μ = частота обработки
* N = количество воркеров

**Условие стабильности:**
```
λ < N × μ
```

#### Обеспечение
* Token buckets (корзины токенов) для каждого тенанта
* Dominant Resource Fairness (DRF)
* Circuit breaker → HTTP 503

---

### 10. SLO по задержкам (Latency)
Цель:
```
P95 ≤ 60 сек
```
Разбивка:
* Очередь: 5 сек
* Выполнение: 50 сек
* Хранилище: 4 сек
* Управление: 1 сек

---

### 11. Мульти-региональная стратегия
Топология: Active / Passive.
Поведение при отказе:
* Репликация БД
* Очередь восстанавливается из БД
* Задачи безопасно перезапускаются
**Гарантия:** Отсутствие потерь, ограниченное дублирование.

---

### 12. Компромиссы (Tradeoffs)

#### Строгая согласованность vs Пропускная способность
* SERIALIZABLE увеличивает частоту абортов транзакций (~15%)
* Это цена, которую мы платим за корректность

#### Дублирование vs Доступность
* Мы предпочитаем дублирующее выполнение потере данных

#### Задержка vs Безопасность
* Ретраи/бэк-оффы увеличивают задержку хвоста (tail latency)
* Это предотвращает повреждение данных

---

### 13. Почему не существующие системы?
| Система    | Ограничение                               |
| ---------- | ----------------------------------------- |
| Kubernetes | Нет гарантий выполнения на уровне приложения |
| Kafka      | Отсутствует семантика выполнения          |
| Spanner    | Только хранилище                          |

SGR Kernel обеспечивает:
> **Корректность выполнения, а не просто планирование или хранение**

---

### 14. Заключение
SGR Kernel определяет новую абстракцию:
> **Выполнение как формально проверяемая граница системы**

Это превращает распределенное выполнение из принципа «максимальных усилий» (best-effort) в **доказуемую корректность при сбоях**.

---

### 15. Открытые вопросы
* Формальная верификация (TLA+)
* Устойчивость к византийским ошибкам (будущие работы)
* Модели планирования с учетом стоимости
* Семантика мульти-региональной работы active/active

---
---

## [EN] ENGLISH VERSION (ORIGINAL)

### Status
Draft (L8 Candidate — Distinguished Systems Tier)

### Authors
SGR Kernel Engineering

### Reviewers
Principal / Staff Distributed Systems Engineers

---

### 1. Abstract
SGR Kernel is a deterministic execution layer designed to provide **provable correctness guarantees** for distributed job execution under partial failure, contention, and network asynchrony.

Unlike traditional orchestration systems (e.g. Kubernetes), which guarantee infrastructure-level scheduling, SGR Kernel guarantees:
* **Execution exclusivity**
* **At-least-once delivery with bounded duplication**
* **Atomic visibility of side effects**
* **Eventual progress under bounded contention**

The system formalizes correctness through explicit invariants, failure-domain isolation, and storage-level idempotency.

---

### 2. Motivation
Modern distributed systems lack a **trustworthy execution boundary**.

Existing systems:
* schedule compute (Kubernetes)
* transport messages (Apache Kafka)
* store data (Google Spanner)

But none guarantee:
> “A task executes correctly exactly once in the presence of retries, crashes, and partial commits.”

This gap leads to:
* duplicate side effects
* inconsistent state transitions
* unbounded retry amplification
* undefined behavior under failure

SGR Kernel addresses this by acting as a **Correctness Layer** between intent (job submission) and execution.

---

### 3. Non-Goals
* Not an agent framework
* Not a workflow engine
* Not a general-purpose scheduler
* Not a UI or developer platform

SGR Kernel is strictly:
> **A minimal execution kernel with formally defined guarantees**

---

### 4. System Model

#### 4.1 Components
* **Control Plane**
  * Orchestrator API
  * Primary DB (source of truth)
* **Execution Plane**
  * Stateless workers
  * Isolated runtime environments
* **Queue Layer**
  * Ephemeral transport (non-durable)
* **Storage Layer**
  * Object storage (idempotent writes)

---

#### 4.2 State Machine
Job lifecycle:
```
CREATED → QUEUED → RUNNING → COMPLETED | FAILED
```
Transitions are enforced via:
* Compare-And-Swap (CAS)
* Lease ownership
* Version monotonicity

---

#### 4.3 Source of Truth
* **Database = single source of truth**
* Queue = optimization only
* Storage = side-effect sink

---

### 5. Formal Invariants

#### I1: Execution Exclusivity
At most one worker can hold a valid lease for a job.
**Enforcement:**
* CAS on `lease_version`
* SERIALIZABLE isolation

---

#### I2: At-Least-Once Delivery
Every job is eventually executed.
**Enforcement:**
* Durable `CREATED` state
* Reconciler re-enqueue

---

#### I3: Bounded Duplication
Duplicate execution attempts per lease cycle ≤ 1
**Enforcement:**
* Lease expiry + safety margin
* CAS rejection of stale workers

---

#### I4: Atomic Visibility
No partial results are externally visible.
**Enforcement:**
* Commit marker protocol in object storage

---

#### I5: Eventual Progress
All jobs complete under bounded contention.
**Enforcement:**
* Admission control
* Retry budgets + jitter
* Priority escalation

---

### 6. Failure Model

#### Assumptions
* Crash-stop failures only
* No Byzantine workers
* Eventual network recovery
* Asynchronous system

Time authority:
* DB `CURRENT_TIMESTAMP` is canonical
* Local clocks are untrusted

---

### 7. Failure Scenarios (Proof Sketches)

#### Scenario A: Worker Crash During Execution
* Lease expires
* Reconciler requeues job
**Guarantee:** No lost execution, duplicate bounded.

#### Scenario B: Duplicate Workers
* Two workers attempt same job
**Outcome:** Only one CAS succeeds.
**Guarantee:** No concurrent execution.

#### Scenario C: Zombie Worker
* Worker resumes after lease loss
**Outcome:** CAS fails on commit
**Guarantee:** No stale writes.

#### Scenario D: Queue Loss (Redis failure)
* Queue state disappears
**Outcome:** Reconciler rebuilds from DB.
**Guarantee:** No job loss.

#### Scenario E: DB Outage During Commit
* Worker completes but cannot persist
**Outcome:** Job re-executed
**Guarantee:** Correctness preserved via idempotency.

---

### 8. Storage Contract
SGR Kernel requires:
> **All side effects must be idempotent**

#### Commit Protocol
1. Write to versioned path:
   ```
   /job_id/v_<attempt_id>/data
   ```
2. Validate checksum
3. Write commit marker:
   ```
   /job_id/_SUCCESS
   ```
Consumers: read only after `_SUCCESS`.

---

### 9. Queue Stability & Admission Control
Let:
* λ = arrival rate
* μ = processing rate
* N = workers

**Stability condition:**
```
λ < N × μ
```

#### Enforcement
* Per-tenant token buckets
* Dominant Resource Fairness (DRF)
* Circuit breaker → HTTP 503

---

### 10. Latency SLO
Target:
```
P95 ≤ 60s
```
Decomposition:
* Queue: 5s
* Execution: 50s
* Storage: 4s
* Control: 1s

---

### 11. Multi-Region Strategy
Topology: Active / Passive.
Failover behavior:
* DB replicated
* Queue rebuilt from DB
* Jobs replayed safely
**Guarantee:** No loss, bounded duplication.

---

### 12. Tradeoffs

#### Strong Consistency vs Throughput
* SERIALIZABLE increases abort rate (~15%)
* Accepted for correctness

#### Duplication vs Availability
* Prefer duplicate execution over data loss

#### Latency vs Safety
* Retry/backoff increases tail latency
* Prevents corruption

---

### 13. Why Not Existing Systems?
| System     | Limitation                                |
| ---------- | ----------------------------------------- |
| Kubernetes | No application-level execution guarantees |
| Kafka      | No execution semantics                    |
| Spanner    | Storage only                              |

SGR Kernel provides:
> **Correctness of execution, not just scheduling or storage**

---

### 14. Conclusion
SGR Kernel defines a new abstraction:
> **Execution as a formally verifiable system boundary**

It transforms distributed execution from best-effort into **provable correctness under failure**.

---

### 15. Open Questions
* Formal verification (TLA+)
* Byzantine tolerance (future work)
* Cost-aware scheduling models
* Cross-region active/active semantics

---
