# Integration: PEFT Research Platform (PEFTlab)

The **SGR Kernel** coordinates with the standalone `peftlab` platform as an external tool/plugin. This guide explains the architectural boundaries between the two projects and how to utilize the Kernel as an orchestration wrapper for PEFT (Parameter-Efficient Fine-Tuning) workflows.

## 1. Architectural Overview

While the SGR Kernel excels at multi-step reasoning, RAG, and general-purpose planning, it is **not** an ML training backend. 

Instead, the `PEFTlab` repository handles the heavy GPU lifting (PyTorch, BitsAndBytes, HuggingFace TRL). The SGR Kernel no longer embeds PEFT code directly; instead, it leverages its `run_command` capabilities (or generic CLI execution skills) to invoke PEFTlab as an external process.

**The Boundary:**
*   **SGR Kernel**: Generates experiment configurations (YAML/JSON), orchestrates execution order, handles failure retries via the CLI, and analyzes the resulting logs/artifacts.
*   **PEFT Platform (`peftlab`)**: A standalone CLI platform that executes the raw Python processes, manages VRAM, quantization maps, and writes adapter binaries autonomously.

## 2. Configuration & Dependencies

To execute PEFT jobs via the kernel, the autonomous agent only needs access to the `peftlab` CLI.

```bash
# In the PEFTlab repository (C:\Users\macht\Scar\PEFTlab)
pip install -e .
```

Verify that the `peftlab` command is available in your PATH.

## 3. The Decoupled Execution Flow

When the SGR Kernel runs a PEFT experiment, the flow looks like this:

1.  **Config Generation**: The Kernel's agent writes a standard PEFTlab configuration file (e.g., `bench.yaml`) defining the base model, dataset, and LoRA parameters.
2.  **Execution**: The Kernel executes the external command:
    ```bash
    peftlab run --config bench.yaml
    ```
3.  **Observation**: The Kernel monitors standard output and reads the structured output artifacts (metadata, validation loss, runtime metrics) generated in PEFTlab's artifact directory.
4.  **Decision Loop**: If the performance is suboptimal, the Kernel's reasoning engine modifies `bench.yaml` and deploys a new trial.

## 4. Triggering a Job Programmatically

If you are using the SGR Kernel programmatically without a full autonomous agent, you can dispatch the task using a generic CLI execution skill:

```python
import asyncio
from core.skill_interface import SkillContext
from core.execution import ExecutionState
from skills.cli_executor.handler import CLIExecutorSkill

async def run_peft_experiment():
    skill = CLIExecutorSkill()
    
    ctx = SkillContext(
        config={
            "command": "peftlab run --config /path/to/generated/config.yaml",
            "working_dir": "/path/to/experiment/dir",
            "timeout_seconds": 3600
        },
        execution_state=ExecutionState(request_id="peft-run-001", input_payload="")
    )

    # The SGR Kernel handles process execution, stdout monitoring, and timeouts
    result = await skill.execute(ctx)
    print("Execution complete. Check artifacts directory for weights.")

asyncio.run(run_peft_experiment())
```

## 5. Security and Sandboxing

Training tasks run arbitrary code implicitly. By decoupling PEFTlab, the SGR Kernel agent can safely execute the `peftlab` CLI inside an isolated container or Docker Sandbox without risking the main Kernel's memory space.

---

# Russian Section / Русская Секция 🇷🇺

# Интеграция: Платформа исследований PEFT (PEFTlab)

**SGR Kernel** координирует работу с независимой платформой `peftlab` как с внешним инструментом/плагином. Это руководство объясняет архитектурные границы между двумя проектами и описывает, как использовать ядро в качестве оркестратора для рабочих процессов PEFT (Parameter-Efficient Fine-Tuning).

## 1. Обзор Архитектуры

Хотя SGR Kernel отлично справляется с многошаговыми рассуждениями, RAG и общим планированием, он **не является** бэкендом для ML-обучения.

Вместо этого репозиторий `PEFTlab` берет на себя тяжелую нагрузку на GPU (PyTorch, BitsAndBytes, HuggingFace TRL). SGR Kernel больше не встраивает код PEFT напрямую; вместо этого он использует свои возможности `run_command` (или универсальные навыки выполнения CLI) для запуска PEFTlab как внешнего процесса.

**Граница ответственности:**
*   **SGR Kernel**: Генерирует конфигурации экспериментов (YAML/JSON), оркестрирует порядок выполнения, обрабатывает повторы при сбоях через CLI и анализирует полученные логи/артефакты.
*   **Платформа PEFT (`peftlab`)**: Автономная CLI-платформа, которая выполняет процессы Python, управляет VRAM, словарями квантования и самостоятельно записывает бинарники адаптеров.

## 2. Конфигурация и Зависимости

Для выполнения задач PEFT через автономного агента ядра требуется только доступ к CLI `peftlab`.

```bash
# В репозитории PEFTlab (C:\Users\macht\Scar\PEFTlab)
pip install -e .
```

Убедитесь, что команда `peftlab` доступна в вашем PATH.

## 3. Разделенный Поток Выполнения

Когда SGR Kernel запускает PEFT-эксперимент, поток выглядит так:

1.  **Генерация конфигурации**: Агент ядра записывает стандартный конфигурационный файл PEFTlab (например, `bench.yaml`), определяющий базовую модель, датасет и параметры LoRA.
2.  **Выполнение**: Ядро выполняет внешнюю команду:
    ```bash
    peftlab run --config bench.yaml
    ```
3.  **Наблюдение**: Ядро следит за стандартным выводом и считывает структурированные артефакты (метаданные, потери на валидации, метрики времени выполнения), сгенерированные в директории артефактов PEFTlab.
4.  **Цикл принятия решений**: Если производительность субоптимальна, механизм рассуждений ядра модифицирует `bench.yaml` и запускает новое испытание (Trial).

## 4. Запуск задачи программно

Если вы используете SGR Kernel программно без полноценного автономного агента, вы можете отправить задачу, используя универсальный навык выполнения CLI:

```python
import asyncio
from core.skill_interface import SkillContext
from core.execution import ExecutionState
from skills.cli_executor.handler import CLIExecutorSkill

async def run_peft_experiment():
    skill = CLIExecutorSkill()
    
    ctx = SkillContext(
        config={
            "command": "peftlab run --config /path/to/generated/config.yaml",
            "working_dir": "/path/to/experiment/dir",
            "timeout_seconds": 3600
        },
        execution_state=ExecutionState(request_id="peft-run-001", input_payload="")
    )

    # SGR Kernel обрабатывает выполнение процесса, мониторинг stdout и таймауты
    result = await skill.execute(ctx)
    print("Execution complete. Check artifacts directory for weights.")

asyncio.run(run_peft_experiment())
```

## 5. Безопасность и Песочницы (Sandboxing)

Задачи по обучению неявно требуют выполнения кода. Благодаря отделению PEFTlab от ядра, агент SGR Kernel может безопасно выполнять CLI `peftlab` внутри изолированного контейнера или Docker Sandbox, не подвергая риску пространство памяти основного Ядра.
