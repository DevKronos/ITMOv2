# Implementation Plan: прочитать текущий город
Дата 25.10.2026; spec.md, ui-spec.md, logic-spec.md и contracts/read-city.md согласованы.
## Summary
POST форма → main → storage.mark_city_read(expected_city) → атомарный SQL → redirect → Jinja.
## Technical Context
Python 3.14.4 в существующей .venv (проект требует 3.11+), FastAPI/Jinja2/SQLite.
Только стандартные sqlite3 и текущие зависимости. Существующая локальная БД, одна запись preferences.
Автоматические pytest/TestClient/BeautifulSoup; временные базы, без сети.
## Constitution Check
До и после проектирования PASS: данные сохраняются, слои соблюдены, миграций/пакетов нет,
контракт предшествует коду, полные сценарии проверяются.
## Project Structure
- app/storage.py: транзакция с проверкой ожидаемого города.
- app/main.py: обязательный Form expected_city и mapping ValueError → back.
- app/templates/index.html: форма и disabled state.
- tests/test_sdd_features.py: HTTP, SQL, ошибки, повтор, совместимость поиска.
## Phases
0. Исследование existing unread/normalize_city/connection — research.md.
1. Данные и контракт — data-model.md, contracts/read-city.md, quickstart.md.
2. Контрактные тесты, storage, HTTP/UI, интеграционные проверки по tasks.md.
## Риски и решения
connection() уже делает начальный commit; BEGIN IMMEDIATE ставится после инициализации.
Сначала блокировка, затем SELECT и UPDATE; отдельный SELECT до транзакции недопустим.
Добавленные после commit уведомления могут остаться новыми; это ожидаемо.

## Поддержка демонстрации
scripts/demo_lab05.py создаёт только новую временную базу и исторические уведомления
на фиксированное 2026-10-07T12:00:00+03:00; настоящие даты акций не меняются.
Режим --smoke запускает отдельный uvicorn на свободном loopback-порту, проверяет
HTTP формы и сохранение отметок после реального перезапуска процесса.
