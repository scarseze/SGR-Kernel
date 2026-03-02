# 📊 Телеметрия и Наблюдаемость (Observability)

SGR Kernel предоставляет мощную подсистему телеметрии уровня Enterprise, которая обеспечивает полный контроль над состоянием агентов, графом выполнения задач и производительностью LLM.

## 🔑 Ключевые возможности

1. 🌐 **Распределенная трассировка (Distributed Tracing)**
   Ядро автоматически интегрируется с **OpenTelemetry (OTEL)**. Каждый шаг выполнения агента, каждый вызов LLM и каждый переход по графу сопровождается уникальным `Trace ID` и `Span ID`.
   - Полная поддержка `W3C Trace Context`.
   - Экспорт в Jaeger, Zipkin или любой-другой OLTP-совместимый бэкенд.

2. 📈 **Метрики и Мониторинг (Metrics)**
   SGR Kernel отдает метрики в формате **Prometheus** (обычно на эндпоинте `/metrics`). 
   Собираемые данные:
   - `sgr_agent_execution_time_seconds`: Время работы агента.
   - `sgr_llm_tokens_total`: Расход токенов (входящие/исходящие) в разрезе провайдеров (OpenAI, Anthropic, локальные модели).
   - `sgr_queue_depth`: Глубина очередей задач и задержка брокера сообщений.
   - `sgr_error_rate`: Количество неудачных попыток вызова `tools` агентами.

3. 🗂️ **Структированное логирование (Structured Logging)**
   Все логи ядра пишутся в формате JSON (JSON Lines), что идеально подходит для сбора с помощью Fluent Bit, Logstash или Vector.
   - В логах всегда присутствуют контекстные поля: `agent_id`, `task_id`, `trace_id`.
   - Поддержка динамического изменения уровня логирования (`DEBUG`, `INFO`, `WARNING`, `ERROR`) без перезагрузки системы.

## 🏗️ Архитектура системы логов

Агенты SGR Kernel могут работать в высоконагруженных распределенных средах. В отличие от простых скриптов, ядро собирает телеметрию **асинхронно**, используя легковесные пулы потоков, чтобы логирование не блокировало критический путь выполнения LLM (Zero-overhead observability).

```python
# Пример настройки сборщика метрик
from sgr_kernel.core.telemetry import init_telemetry

init_telemetry(
    service_name="payment_agent",
    endpoint="http://otel-collector:4317",
    enable_metrics=True,
    enable_tracing=True
)
```

## 📊 Дашборды Grafana

В папке `grafana/` (появится в следующих версиях) мы предоставляем готовые дашборды для мониторинга:

* **Cost Overview**: Финансовый мониторинг расходов на API по ключам.
* **Agent Performance**: Эффективность выполнения цепочек размышлений.

---

## 🇺🇸 English

# 📊 Telemetry and Observability

SGR Kernel provides a powerful Enterprise-grade telemetry subsystem that gives you complete control over agent states, task execution graphs, and LLM performance.

## 🔑 Key Features

1. 🌐 **Distributed Tracing**
   The kernel seamlessly integrates with **OpenTelemetry (OTEL)**. Every agent execution step, LLM call, and graph transition is accompanied by a unique `Trace ID` and `Span ID`.
   - Full support for `W3C Trace Context`.
   - Export to Jaeger, Zipkin, or any other OTLP-compatible backend.

2. 📈 **Metrics & Monitoring**
   SGR Kernel exposes metrics in **Prometheus** format (typically on the `/metrics` endpoint).
   Collected data includes:
   - `sgr_agent_execution_time_seconds`: Agent execution duration.
   - `sgr_llm_tokens_total`: Token consumption (input/output) grouped by providers (OpenAI, Anthropic, local models).
   - `sgr_queue_depth`: Task queue depth and message broker latency.
   - `sgr_error_rate`: Rate of failed `tools` executions by agents.

3. 🗂️ **Structured Logging**
   All kernel logs are output in JSON format (JSON Lines), making them perfect for ingestion by Fluent Bit, Logstash, or Vector.
   - Contextual fields are always present: `agent_id`, `task_id`, `trace_id`.
   - Support for dynamic log level adjustments (`DEBUG`, `INFO`, `WARNING`, `ERROR`) without system restarts.

## 🏗️ Logging Architecture

SGR Kernel agents can operate in highly loaded distributed environments. Unlike simple scripts, the kernel collects telemetry **asynchronously** using lightweight thread pools, ensuring that logging does not block the critical path of LLM execution (Zero-overhead observability).

```python
# Setup example
from sgr_kernel.core.telemetry import init_telemetry

init_telemetry(
    service_name="payment_agent",
    endpoint="http://otel-collector:4317",
    enable_metrics=True,
    enable_tracing=True
)
```

## 📊 Grafana Dashboards

In the `grafana/` directory (coming in future releases) we provide out-of-the-box dashboards for monitoring:

* **Cost Overview**: Financial tracking of API usage by keys.
* **Agent Performance**: Efficiency tracking of reasoning chains.
