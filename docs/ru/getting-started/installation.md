# Welcome (Onboarding)
> A guide for new developers, AI Engineers, and Analysts.

Welcome to the team! We design AI systems (LLM/RAG/Agents) based on the **Task-driven development** ideology using the **SGR-Kernel-R7** orchestrator.

Below is the process for setting up a workstation in 30 minutes.

## 1. Permissions and Access (Where to get keys?)
You will need:
- **Git Access:** Access to the `ai_ml_playbook` repository and internal SGR-Kernel skills.
- **SGR-Kernel API Key (Test Keys):** Test keys for the sandbox are issued by the `MLOps Engineer` upon request. They contain strict limits on billing.
- **S3 / VectorDB Credentials:** `Read-Only` access to Staging buckets containing data.

## 2. Environment Setup (Local)
If you are on **Windows**, follow the instructions in [testing_and_deployment_guide_windows.md](testing_and_deployment_guide_windows.md) (via WSL2). If on Ubuntu/Linux — [testing_and_deployment_guide.md](testing_and_deployment_guide.md).

**Briefly:**
1. Install Docker and NVIDIA Container Toolkit.
2. Clone SGR-Kernel: `git clone https://github.com/scarseze/SGR-Kernel-R7.git`
3. Create a virtual environment: `python3 -m venv venv && source venv/bin/activate`
4. Run the installation: `pip install -r requirements.txt`

## 3. Your First Task
Learning is best done through practice. Try running a test local experiment:
1. Examine the architecture: `AGENTS.md`.
2. Locate the test file `templates/manifest_template.json`.
3. Run the SGR-Kernel orchestrator: 
   ```bash
   python main.py --experiment templates/manifest_template.json
   ```
4. Examine the logs (WAL) that the Kernel will save after execution.

For all questions (configurations, access, OOM errors), contact your `MLOps Engineer`.

---

# Russian Section / Русская Секция 🇷🇺

# Добро пожаловать (Onboarding)
> Гайд для новых разработчиков, AI-инженеров и Аналитиков.

Добро пожаловать в команду! Мы проектируем AI-системы (LLM/RAG/Agents) на основе идеологии **Task-driven development** с использованием оркестратора **SGR-Kernel-R7**.

Ниже описан процесс настройки рабочего места за 30 минут.

## 1. Разрешения и Доступы (Где взять ключи?)
Вам потребуются:
- **Git Access:** Доступ к репозиторию `ai_ml_playbook` и внутренним скиллам SGR-Kernel.
- **SGR-Kernel API Key (Test Keys):** Тестовые ключи для песочницы выдаются `MLOps Engineer` по запросу. Они содержат лимиты (limits) на биллинг.
- **S3 / VectorDB Credentials:** Читательский доступ (`Read-Only`) к Staging бакетам с данными.

## 2. Настройка Окружения (Локально)
Если у вас **Windows**, следуйте инструкции [testing_and_deployment_guide_windows.md](testing_and_deployment_guide_windows.md) (через WSL2). Если Ubuntu/Linux — [testing_and_deployment_guide.md](testing_and_deployment_guide.md).

**Кратко:**
1. Установите Docker и NVIDIA Container Toolkit.
2. Склонируйте SGR-Kernel: `git clone https://github.com/scarseze/SGR-Kernel-R7.git`
3. Создайте виртуальное окружение: `python3 -m venv venv && source venv/bin/activate`
4. Выполните установку: `pip install -r requirements.txt`

## 3. Ваша первая задача
Обучение лучше всего проходит на практике. Попробуйте запустить тестовый локальный эксперимент:
1. Посмотрите на архитектуру: `AGENTS.md`.
2. Найдите тестовый файл `templates/manifest_template.json`.
3. Запустите оркестратор SGR-Kernel: 
   ```bash
   python main.py --experiment templates/manifest_template.json
   ```
4. Изучите логи (WAL), которые Kernel сохранит после выполнения.

По всем вопросам (конфигурации, доступы, ошибки OOM (Out Of Memory)) обращайтесь к вашему `MLOps Engineer`.
