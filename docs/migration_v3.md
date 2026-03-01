# Migration Guide: SGR Kernel v2 → v3.0 (Swarm of Swarms)

## Breaking Changes

### 1. `Agent` model now includes `supported_modalities`
Default: `["text"]`. No action required for existing text-only agents.

### 2. New classes: `SubSwarmAgent`, `TransferToSubSwarm`
- `SubSwarmAgent` extends `Agent` with `is_sub_swarm: bool` and `sub_swarm_config: Optional[Dict]`.
- `TransferToSubSwarm` extends `TransferToAgent` with `return_to_parent_on_complete: bool`.

### 3. `SwarmEngine.execute()` signature change
- Added `_swarm_depth: int = 0` parameter (internal, do not set manually).
- `messages` type changed: `List[Dict[str, str]]` → `List[Dict[str, Any]]` to support multimodal payloads.

### 4. `TransferToAgent` import path unchanged
```python
# Still works:
from core.agent import TransferToAgent
# New imports:
from core.agent import SubSwarmAgent, TransferToSubSwarm
```

## Upgrade Steps
1. Update `core/agent.py` and `core/swarm.py` from the latest release.
2. If you have custom skills returning `TransferToAgent`, ensure the `agent` field is compatible.
3. For sub-swarm features, return `TransferToSubSwarm(agent=SubSwarmAgent(...), context_message="...")`.
4. Set `COMPLIANCE_LEVEL=gdpr|hipaa|rf_152fz` in env for regulated workloads.

## 🇷🇺 Российская локализация (152-ФЗ)

### Новые возможности:
- Конфиг `configs/compliance/rf_152fz_example.yaml` с предустановленными паттернами ПДн РФ.
- Интеллектуальная маскировка (Паспорт РФ, СНИЛС, ИНН, Российские телефоны).

### Возможные ошибки с БД (Breaking Changes):
- При `COMPLIANCE_LEVEL=rf_152fz` **запрещена** работа с базами данных, хостящимися вне зон `.ru`, `ru-`, `localhost`, или локального `sqlite`. Попытка подключиться к заграничной БД (`eu-west-1`, `us-east` и т.д.) вызовет `ValueError` с критической ошибкой Data Localization.

### Миграция:
1. Разверните инфраструктуру БД и серверов в РФ (Yandex Cloud, VK Cloud, Selectel, On-Prem).
2. Обновите `.env` файл: `COMPLIANCE_LEVEL=rf_152fz`
3. Убедитесь, что `MEMORY_DB_URL` указывает на российскую ноду.
