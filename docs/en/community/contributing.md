# Contributing to ai_ml_playbook / Руководство по внесению вклада

---

## 🇷🇺 Русский (Russian)

### Кто может делать вклад?
Любой член команды AI/ML Department: Data Engineer, RAG Specialist, LLM Evaluator, MLOps Engineer, Product Owner.

### Ветки (Branches)
| Тип изменения | Шаблон ветки |
| :--- | :--- |
| Новая фича / рабочий процесс | `feat/<task-id>-short-desc` |
| Исправление ошибки в документе | `fix/<task-id>-short-desc` |
| Обновление промпта | `prompt/<agent-name>-v<version>` |
| Обновление манифеста/конфига | `manifest/<experiment-name>` |

### Правила коммитов
Используйте формат: `type(scope): описание`

```
feat(rag): add hybrid BM25+vector retrieval workflow
fix(onboarding): correct API key setup steps
prompt(router-agent): v3 with improved fallback handling
```

### Чеклист перед Pull Request
1. [ ] Заполнен `templates/task_template.md` (гипотеза, метрики, бюджет).
2. [ ] Промпт прошёл eval-тесты (см. `docs/workflows/evaluation_loop.md`).
3. [ ] PII очищены из всех примеров и датасетов.
4. [ ] `manifest.json` содержит Quad-Versioning (Код, Данные, Модель, Промпт).
5. [ ] Заполнен `templates/pull_request_template.md`.
6. [ ] Запрошен аппрув `MLOps Engineer`.

---

## 🇺🇸 English

### Who can contribute?
Any member of the AI/ML Department: Data Engineer, RAG Specialist, LLM Evaluator, MLOps Engineer, Product Owner.

### Branches
| Change Type | Branch Pattern |
| :--- | :--- |
| New feature / workflow | `feat/<task-id>-short-desc` |
| Document fix | `fix/<task-id>-short-desc` |
| Prompt update | `prompt/<agent-name>-v<version>` |
| Manifest / config update | `manifest/<experiment-name>` |

### Commit Convention
Use the format: `type(scope): description`

```
feat(rag): add hybrid BM25+vector retrieval workflow
fix(onboarding): correct API key setup steps
prompt(router-agent): v3 with improved fallback handling
```

### Pull Request Checklist
1. [ ] `templates/task_template.md` is filled (hypothesis, acceptance metrics, budget cap).
2. [ ] Prompt passed eval tests (see `docs/workflows/evaluation_loop.md`).
3. [ ] All PII stripped from examples and datasets.
4. [ ] `manifest.json` has Quad-Versioning (Code, Data, Model, Prompt hashes).
5. [ ] `templates/pull_request_template.md` is filled out.
6. [ ] `MLOps Engineer` approval requested.
