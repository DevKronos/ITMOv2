# Tasks: прочитать текущий город
## Подготовка
- [x] T001 Проверить .specify/memory/constitution.md, согласовать ui-spec.md/logic-spec.md/contracts/read-city.md.
## US1: массовое прочтение (P1)
- [x] T002 [US1] Добавить контрактные и HTTP тесты в tests/test_sdd_features.py для FR-001…005/004a.
- [x] T003 [US1] Добавить mark_city_read в app/storage.py: expected_city «непустая строка длиной <=100 до нормализации»; атомарная проверка и UPDATE, int>=0.
- [x] T004 [US1] Добавить POST и сообщения в app/main.py; форму и disabled в app/templates/index.html.
## Интеграция
- [x] T005 Запустить scripts/check.py, node hook suite; результаты practices/practice_05/results.
- [x] T006 Подготовить practices/practice_05/demo.md, testing.md, comparison/reflection и проверить соответствие контракту.
Зависимости: T001→T002→T003→T004→T005→T006.
MVP: US1 полностью. Независимая проверка: действие над историей двух городов.
