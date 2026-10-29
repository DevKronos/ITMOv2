# Proposal
## Why
Сохранённый каталог содержит много предложений и длинные условия.
Поиск по тексту сократит ручной просмотр, не обращаясь к источнику.
## What Changes
- GET форма q, число найденных записей, сброс и состояние без совпадений.
- Нормализованный поиск в title и conditions; ограничение 100 символов.
## Capabilities
### New Capabilities
- `catalog-search`: локальный поиск без изменения сохранённых данных.
### Modified Capabilities
Нет.
## Impact
app/domain.py, app/main.py, app/templates/index.html, tests/test_sdd_features.py.
API state, CLI, MCP, подписки и подбор уведомлений не меняются. Новых зависимостей нет.
