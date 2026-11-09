# OpenSpec и GitHub Spec Kit: сравнение по выполненной работе

Использованы [OpenSpec 1.14.1](https://github.com/Fission-AI/OpenSpec) и
[GitHub Spec Kit / specify-cli 1.2.3](https://github.com/github/spec-kit).
Официальные источники workflow: [OpenSpec CLI](https://openspec.dev/docs/cli),
[Spec Kit core](https://github.com/github/spec-kit/blob/main/docs/reference/core.md).
Для точных флагов использован --help реально установленных версий, не только web.
Spec Kit — полноценный процесс constitution/specify/plan/tasks/implement и анализ,
а не произвольное имя папки с Markdown.

| Аспект | OpenSpec: поиск | Spec Kit: прочтение города |
|---|---|---|
| Установка | npm install --prefix .sdd-tools @fission-ai/openspec@1.14.1; Node 22.22.1 | pip install specify-cli==1.2.3 в локальную .venv; Python 3.14.4 |
| Настройка | init --tools codex --language Russian; создано 6 skills | init --here --integration codex --integration-options=--skills; 10 skills, bundled workflow |
| Создание требований | new change и instructions задают proposal/specs/design/tasks | constitution и spec-template задают User Story P1, FR/SC, assumptions; UI и logic — отдельные дополнения |
| Документация | Изменение и delta на capability catalog-search, затем main spec | Полная папка specs/001-read-city-notifications: spec, research, plan, data-model, contracts, tasks, analysis |
| Согласование | Review уточнил полные conditions, нормализацию и длину; strict validate проверил структуру | Сопоставлены UI/logic: expected_city, rowcount, stale form, ошибки; чеклист и analyze связывают FR с T001…006 |
| Изменения | Архиватор реально перенёс change в датированный archive и создал main spec | Хранятся единые spec/plan/tasks; штатного аналогичного archive в применённом цикле нет |
| Связь с кодом | instructions apply перечислил файлы и задачи; 58 тестов после первой фичи | Задачи с ID, Story и путями; контракт напрямую проверяется HTTP→storage→HTML |
| Проверка | validate --strict проверяет SHALL и Scenario, но не исполнение; pytest доказывает поведение | check-prerequisites проверяет наличие документов; тесты отдельно |
| Codex | Локальные .agents/skills/openspec-*; применены инструкции propose/apply/archive | .agents/skills/speckit-*; применены specify/plan/tasks/analyze/implement, setup-plan/setup-tasks скрипты |
| Сильная сторона | Для маленького изменения явный delta и штатная синхронизация конечного контракта | Разделение пользовательской цели, технического плана, данных и интерфейсов помогло найти проблему старой вкладки |
| Ограничение | Структурный PASS не проверяет HTML, XSS или сохранение данных | Больше документов и ручной проверки, скрипты не доказывают согласованность типов/ошибок |
| Соответствие проекту | Лёгкое добавление одной capability к существующему каталогу | Полезен для сценария через несколько слоёв с транзакционным предусловием |

По практическому объёму OpenSpec оказался удобнее для небольшой фичи: есть строгая
структура требований и готовое архивирование. Spec Kit дал больше пользы при
согласовании интерфейса с логикой: в data-model/contract пришлось явно определить,
что считать текущим городом и когда проверять его. Эта польза обусловлена процессом
проверки, а не автоматической гарантией инструмента.

