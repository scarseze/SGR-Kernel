# SGR Kernel: First Run & Quickstart

Welcome to the **SGR Kernel**! This guide will walk you through setting up the repository from scratch, verifying the environment, and running your very first autonomous task.

## 1. Prerequisites
Before starting, ensure you have the following installed:
*   **Python:** 3.10+ (Recommended: 3.11)
*   **OS:** Linux, WSL, macOS, or Windows
*   **Docker:** (Optional but deeply recommended for Sandboxed Code Execution)

## 2. Environment Setup

Clone the repository and set up an isolated Python environment.

```bash
git clone <repo_url>
cd sgr_kernel

# Create a virtual environment
python -m venv .venv

# Activate the environment
# On Linux/macOS:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate

# Install the kernel and its dependencies
pip install -e .
```

## 3. Configuration (.env)

The kernel relies heavily on environment variables for LLM API access, telemetry, and storage. Create a `.env` file in the root directory:

```bash
cp .env.example .env
```
*(If `.env.example` is missing, create `.env` manually)*

**Minimal `.env` setup:**
```ini
# Core LLM settings
OPENAI_API_KEY="sk-your-key-here"
# If using Anthropic, Ollama, or vLLM:
LLM_BASE_URL="https://api.openai.com/v1" 

# Storage Configuration
ARTIFACT_STORAGE_PATH="./artifacts"
CHECKPOINT_PATH="./checkpoints"

# Optional: Redis for distributed task queues
REDIS_URL="redis://localhost:6379/0"
```

## 4. Verifying the Installation (Running Tests)

Before running the main kernel, ensure your installation is healthy by running the core unit tests. The SGR Kernel has an extensive `pytest` suite.

```bash
pip install pytest pytest-asyncio
python -m pytest tests/ -v
```
You should expect over 90 passing tests. If tests fail, your Python version might be incorrect or dependencies failed to install.

## 5. Your First Run (CLI)

The easiest way to interact with the Kernel natively is via the included `main.py` invocation script.

```bash
python main.py --goal "What is the 50th digit of Pi? Use your web search skill to find out."
```

**What happens next?**
1. The **Planner** receives your goal and decomposes it.
2. The **Router** determines that the `web_search_skill` is the right tool for the job.
3. The **SkillRuntimeAdapter** executes the tool securely.
4. The **Critic** verifies the result and finalizes the step.
5. The result is returned to the console.

## 6. (Bonus) Running the Telegram Bot Interface

If you want a chat-based interface to the kernel, we export a fully functioning Telegram Bot wrapper.

1. Get a Bot Token from the [@BotFather](https://t.me/botfather) on Telegram.
2. Add `TELEGRAM_TOKEN="your-bot-token"` to your `.env` file.
3. Start the bot:
    ```bash
    python interfaces/telegram_bot.py
    ```
4. Send `/start` or a casual message to your bot on Telegram!

## Next Steps
Now that you have the Kernel running, you probably want to write your own custom logic. Check out the [Skill Development Guide](SKILL_DEVELOPMENT.md) to learn how to write new tools (Skills) for the engine!

---

# Russian Section / Русская Секция 🇷🇺

# Ядро SGR: Первый запуск и Quickstart

Добро пожаловать в **SGR Kernel**! Это руководство поможет вам настроить репозиторий с нуля, проверить окружение и запустить вашу самую первую автономную задачу.

## 1. Предварительные требования
Перед началом убедитесь, что у вас установлено следующее:
*   **Python:** 3.10+ (Рекомендуется: 3.11)
*   **ОС:** Linux, WSL, macOS или Windows
*   **Docker:** (Опционально, но настоятельно рекомендуется для безопасного выполнения кода в песочнице)

## 2. Настройка окружения

Склонируйте репозиторий и настройте изолированное Python-окружение.

```bash
git clone <repo_url>
cd sgr_kernel

# Создание виртуального окружения
python -m venv .venv

# Активация окружения
# В Linux/macOS:
source .venv/bin/activate
# В Windows:
.venv\Scripts\activate

# Установка ядра и его зависимостей
pip install -e .
```

## 3. Конфигурация (.env)

Ядро сильно зависит от переменных окружения для доступа к API LLM, телеметрии и хранилища. Создайте файл `.env` в корневой директории:

```bash
cp .env.example .env
```
*(Если файл `.env.example` отсутствует, создайте `.env` вручную)*

**Минимальные настройки `.env`:**
```ini
# Основные настройки LLM
OPENAI_API_KEY="sk-your-key-here"
# При использовании Anthropic, Ollama или vLLM:
LLM_BASE_URL="https://api.openai.com/v1" 

# Конфигурация хранилища
ARTIFACT_STORAGE_PATH="./artifacts"
CHECKPOINT_PATH="./checkpoints"

# Опционально: Redis для распределенных очередей задач
REDIS_URL="redis://localhost:6379/0"
```

## 4. Проверка установки (Запуск тестов)

Перед запуском основного ядра убедитесь, что установка выполнена корректно, запустив базовые unit-тесты. Ядро SGR имеет обширный набор тестов `pytest`.

```bash
pip install pytest pytest-asyncio
python -m pytest tests/ -v
```
Вы должны увидеть более 90 успешно пройденных тестов. Если тесты падают, возможно, у вас неверная версия Python или зависимости не установились должным образом.

## 5. Ваш первый запуск (CLI)

Самый простой способ взаимодействия с ядром напрямую — через включенный скрипт запуска `main.py`.

```bash
python main.py --goal "What is the 50th digit of Pi? Use your web search skill to find out."
```

**Что происходит дальше?**
1. **Планировщик (Planner)** получает вашу цель и разбивает её на части.
2. **Маршрутизатор (Router)** определяет, что навык `web_search_skill` — правильный инструмент для этой задачи.
3. **Адаптер Скиллов (SkillRuntimeAdapter)** безопасно выполняет этот инструмент.
4. **Критик (Critic)** проверяет результат и завершает шаг.
5. Результат возвращается в консоль.

## 6. (Бонус) Запуск интерфейса Telegram-бота

Если вы хотите получить чат-интерфейс к ядру, мы предоставляем полнофункциональную обертку для Telegram-бота.

1. Получите токен бота у [@BotFather](https://t.me/botfather) в Telegram.
2. Добавьте `TELEGRAM_TOKEN="your-bot-token"` в ваш `.env` файл.
3. Запустите бота:
    ```bash
    python interfaces/telegram_bot.py
    ```
4. Отправьте команду `/start` или обычное сообщение вашему боту в Telegram!

## Следующие шаги
Теперь, когда ядро запущено, вы, вероятно, захотите написать собственную логику. Загляните в [Руководство по разработке скиллов](SKILL_DEVELOPMENT.md), чтобы узнать, как создавать новые инструменты (Скиллы) для движка!
