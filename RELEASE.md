# SGR Kernel v3.0 (Gold Master) & PEFTlab v2.9.0 Enterprise

---

## 🇷🇺 Русский (Russian)

### Обзор релиза v3.0: "Swarm of Swarms"
**SGR Kernel v3.0** — это крупнейший корпоративный релиз, вводящий иерархическую оркестрацию агентов и полное соответствие нормативным требованиям РФ и мира.

### Ключевые нововведения
*   **Иерархические Рои**: Агенты могут порождать под-рои для бесконечной глубины рассуждений.
*   **Комплаенс (152-ФЗ, GDPR, HIPAA)**: Маскировка персональных данных (PII) в реальном времени.
*   **Локализация данных**: Жесткая проверка физического расположения баз данных.
*   **Мультимодальность**: Нативная поддержка изображений и аудио.

### Миграция с v2
1. **Lazy Loading**: Убедитесь, что тяжелые зависимости скиллов загружаются динамически.
2. **PostgreSQL**: Версии для продакшена теперь требуют PostgreSQL (вместо SQLite).

---

## 🇺🇸 English

### Release v3.0 Overview: "Swarm of Swarms"
**SGR Kernel v3.0** is a major Enterprise release, introducing hierarchical agent orchestration and full regulatory compliance for global and domestic data processing.

### Key Features
*   **Hierarchical Swarms**: Agents can now spawn sub-swarms for infinite reasoning depth.
*   **Compliance (GDPR, HIPAA, 152-FZ)**: Real-time PII redaction and masking.
*   **Data Localization**: Strict enforcement of database residency for sensitive jurisdictions.
*   **Multimodal**: Native support for LLM vision and audio context.

### Migration from v2
1. **Lazy Loading**: Ensure heavy skill dependencies are strictly lazy-loaded.
2. **Postgres Required**: Shift from experimental SQLite to PostgreSQL for production environments.

---

## Deployment / Развертывание

### 152-FZ (Russia Production)
```bash
export COMPLIANCE_LEVEL=rf_152fz
export DATABASE_HOST=postgres.ru-central1.internal
docker-compose up -d
```

### GDPR (EU Production)
```bash
export COMPLIANCE_LEVEL=gdpr
export DATA_RETENTION_DAYS=90
docker-compose up -d
```
