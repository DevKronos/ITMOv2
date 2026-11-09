# Лабораторная №5: Spec-Driven Development

В существующем приложении [«Акции рядом»](../practice_04/discount-notifier)
реализованы две фичи.

| Фича | Инструмент | Результат |
|---|---|---|
| Поиск по заголовку и полным условиям каталога | OpenSpec 1.14.1 | GET q, нормализация регистра/ё/пробелов, ограничение 100 символов, сброс и пустые состояния |
| Прочтение уведомлений текущего города | GitHub Spec Kit / specify-cli 1.2.3 | HTML форма, атомарная проверка города и SQL отметка, число изменений, защита старой вкладки |

## Материалы

- [Исследование, baseline и выбор фич до реализации](feature-selection.md).
- [Общий контракт](contract.md), [согласование](spec-review.md).
- UI: [до](specs/before/ui-spec.md), [после](specs/after/ui-spec.md).
- Логика: [до](specs/before/logic-spec.md), [после](specs/after/logic-spec.md).
- [Согласованные версии до уточнения FastAPI](specs/after-review-v1) также сохранены.
- [Проверки и таблица сценариев](testing.md), [демо](demo.md).
- [Сравнение фреймворков](framework-comparison.md), [рефлексия](reflection.md).
- [Фактические журналы](results), [контрольные суммы и этапы](results/chronology.json).

## Рабочие SDD-артефакты

OpenSpec: [конфигурация](../practice_04/discount-notifier/openspec/config.yaml),
[архив полного изменения](../practice_04/discount-notifier/openspec/changes/archive/2026-10-25-search-saved-catalog),
[итоговая спецификация](../practice_04/discount-notifier/openspec/specs/catalog-search/spec.md).
Архив содержит Explore, proposal, delta-spec, design, review и выполненные tasks.
Цикл: new change → instructions → документы → strict validate → apply → 58 tests →
validate → archive --yes (синхронизация main spec) → strict validate.

Spec Kit: [.specify](../practice_04/discount-notifier/.specify),
[конституция](../practice_04/discount-notifier/.specify/memory/constitution.md),
[рабочая фича](../practice_04/discount-notifier/specs/001-read-city-notifications).
Цикл: constitution → specify → review UI/logic → plan/research/data-model/contracts →
tasks → analyze → implement → проверки. Использованы настоящие bundled templates,
Codex skills и setup-plan/setup-tasks/check-prerequisites установленного CLI.
Git extension не устанавливался, feature directory задаётся независимо от ветки.

## Реализация

Чистый поиск в app/domain.py; HTTP и сообщения в app/main.py; форма и карточки
в app/templates/index.html; транзакция BEGIN IMMEDIATE в app/storage.py.
Добавлены tests/test_sdd_features.py и scripts/demo_lab05.py.
Новых runtime-зависимостей, таблиц и миграций нет. CLI/MCP/API state сохранены.
Рабочая data/promos.db для тестов не использовалась. Инструменты OpenSpec и
Spec Kit закреплены в .sdd-tools/package-lock.json и .sdd-tools/requirements.txt.

