# 🔄 Руководство по миграции (OSS -> Enterprise)

Переход от базовой (локальной/тестовой) версии SGR Kernel к Enterprise-конфигурации требует изменения механизмов хранения состояния (State Management) и брокеров сообщений для обеспечения горизонтального масштабирования.

Данный документ описывает фундаментальные шаги процесса миграции.

## 1. 🗄️ Базы Данных (Storage Layer)

В локальной версии ядро использует SQLite (`memory.db` и `swarm_chat_history.db`) для удобства разработки. Для Enterprise развертывания необходимо произвести миграцию данных в **PostgreSQL** (рекомендуется версия 15+).

* **Шаг 1:** Разверните кластер PostgreSQL с настроенной репликацией.
* **Шаг 2:** Измените строку подключения (`DATABASE_URL`) в файле конфигурации или `.env` с `sqlite:///...` на `postgresql+asyncpg://user:pass@host/db`.
* **Шаг 3:** Выполните накатывание миграций Alembic: `alembic upgrade head`.

## 2. 📨 Брокер Заданий (Task Broker)

Вместо In-Memory планировщика или SQLite-очередей, Enterprise-окружение требует развертывания In-Memory Data Grid.

* **Шаг 1:** Разверните кластер **Redis** (или KeyDB).
* **Шаг 2:** Укажите `REDIS_URL` в конфигурации.
* **Шаг 3:** Переключите `TaskQueue` реализацию в коде с локальной на `RedisQueue` для поддержки распределенных брокеров и механизма Pub/Sub (используется для подписки UI на события агентов).

## 3. 🧠 RAG и Векторные БД

Если ваш проект использует знания (RAG), локальные базы (например, Chroma local или Annoy) не подойдут для параллельного корпоративного доступа. Смигрируйте векторные эмбеддинги в **Qdrant**, **Pinecone** или **Milvus**.

## 4. 📊 Observability (Телеметрия)

Смотрите раздел [Телеметрия](../telemetry.md). Включите интеграцию с OpenTelemetry-Collector в `fluent-bit.conf`, чтобы логи и трейсы всех микросервисов сводились в единый интерфейс (Kibana/Grafana).

---

## 🇺🇸 English

# 🔄 Migration Guide (OSS to Enterprise)

Transitioning from the basic (local/testing) version of SGR Kernel to a production-ready Enterprise configuration requires fundamental changes to the State Management mechanisms and message brokers to ensure horizontal scalability.

This document outlines the core steps required for migration.

## 1. 🗄️ Relational Databases (Storage Layer)

In the local setup, the kernel leverages SQLite (`memory.db` and `swarm_chat_history.db`) for developer convenience. For an Enterprise deployment, data must be migrated to **PostgreSQL** (version 15+ is recommended).

* **Step 1:** Deploy a provisioned PostgreSQL cluster with replication enabled.
* **Step 2:** Modify the connection string (`DATABASE_URL`) in your configuration file or `.env` from `sqlite:///...` to `postgresql+asyncpg://user:pass@host/db`.
* **Step 3:** Apply the schema via Alembic migrations: `alembic upgrade head`.

## 2. 📨 Distributed Task Broker

Instead of utilizing an In-Memory scheduler or purely SQLite-backed queues, an Enterprise environment strictly requires an In-Memory Data Grid.

* **Step 1:** Deploy a **Redis** cluster (or KeyDB).
* **Step 2:** Populate the `REDIS_URL` in your environment configuration.
* **Step 3:** Switch the kernel's `TaskQueue` implementation from local to `RedisQueue` to robustly support distributed task brokering and the Pub/Sub mechanism (which UI gateways use to stream agent events seamlessly).

## 3. 🧠 RAG and Vector Databases

If your deployment heavily utilizes Retrieval-Augmented Generation (RAG), local ephemeral databases (such as local ChromaDB instances or Annoy) will fail under parallel corporate access loads. You must proactively migrate your vector embeddings into **Qdrant**, **Pinecone**, or **Milvus**.

## 4. 📊 Observability and Telemetry

Refer directly to the [Telemetry](../telemetry.md) section. Enable the OpenTelemetry-Collector integration within `fluent-bit.conf` to guarantee that all microservice logs, traces, and LLM metrics are efficiently consolidated into a single pane of glass (like Kibana or Grafana).
