# Происхождение и локальная адаптация

- Автор: Jesse Vincent; проект [obra/superpowers](https://github.com/obra/superpowers).
- Исходный каталог: `skills/systematic-debugging`.
- Зафиксированный commit: `8ca22dba9a94f28898bbce59f2537ff4d87c747d`
  (2026-09-25, release v6.4.2).
- [Исходный skill на этом commit](https://github.com/obra/superpowers/blob/8ca22dba9a94f28898bbce59f2537ff4d87c747d/skills/systematic-debugging/SKILL.md).
- Лицензия: MIT; полный оригинал с copyright Jesse Vincent сохранён в `LICENSE`.
- Дата проектной установки: 7 октября 2026 года. Установка локальная для OpenCode,
  без plugins, аккаунтов, платных сервисов и изменения глобальной конфигурации.

Это готовый сторонний skill с явно обозначенной адаптацией, не собственная
методика проекта. `UPSTREAM-SKILL.md` — неизменённый оригинал; `SKILL.md` —
загружаемая версия. Перед установкой полностью прочитаны оба исполняемых примера
(`find-polluter.sh`, `condition-based-waiting-example.ts`), SKILL.md и три материала
по трассировке, защите и ожиданию условий.

Изменения только в SKILL.md:

1. Добавлена пометка адаптации и объяснение относительных путей.
2. Два обращения к соседним skills (`superpowers:test-driven-development` и
   `superpowers:verification-before-completion`) заменены самодостаточными шагами:
   минимальное воспроизведение до исправления, повтор воспроизведения и запуск
   `.venv/bin/python scripts/check.py` с проверкой реального результата.
   Другие skills не устанавливались и не требуются.
3. Указано, что npm-скрипт и TypeScript — иллюстрации upstream, не инструменты
   выполнения тестов Python. `find-polluter.sh` использует npm test и подавляет
   его код ошибки; здесь запускать его нельзя и его вывод не подтверждает pytest.
   TypeScript-пример импортирует типы чужого проекта и не самодостаточен.
   Эти файлы сохранены без изменений ради полноты связанных материалов;
   Node/npm, TypeScript и их зависимости не устанавливаются.
4. Добавлены временная APP_DB_PATH и запрет вывода секретов при диагностике.

Четыре фазы, их порядок и основной текст сохранены. Три справочных Markdown,
скрипт, TypeScript-пример и лицензия побайтно совпадают с upstream.
Не установлены `CREATION-LOG.md`, `test-academic.md`, `test-pressure-{1,2,3}.md`:
это материалы разработки/оценки самого skill, не ресурсы его рабочего процесса.
Полный репозиторий Superpowers и его bootstrap/hooks не подключались.

OpenCode поддерживает `.opencode/skills/<name>/SKILL.md` с YAML name/description:
[Agent Skills](https://docs.opencode.ai/docs/skills/).
Наличие файлов и запись в `opencode debug skill` доказывают только обнаружение;
загрузка и применение требуют отдельного агентного запуска с вызовом `skill`.
