# Фактические проверки

Временные SQLite-базы; фон выключен, тесты не запрашивают сайт.
Исходный Git status пуст. Команды выполнялись из discount-notifier.
Изменения сделаны через apply_patch и shell; это ручные запуски checks,
не автоматический PASS OpenCode hook после редактирования.

| Команда/этап | Фактический результат | Журнал |
|---|---|---|
| Baseline scripts/check.py вне sandbox | AST OK, 52 passed in 19.87s | [baseline](results/baseline.txt) |
| После поиска scripts/check.py | AST OK, 58 passed in 19.16s | [feature1](results/feature1-tests.txt) |
| Первая интеграция | 1 failed, 60 passed: пустой Form даёт 422 | [FAIL](results/first-integration-failure.txt) |
| После уточнения контракта scripts/check.py | AST OK, 61 passed in 20.72s, exit 0 | [final](results/final-python.txt) |
| scripts/demo_lab05.py --smoke | PASS, реальный uvicorn, HTTP, перезапуск | [smoke](results/process-smoke.txt) |
| node --test .opencode/tests/python-check.test.mjs | 1 top-level test passed, 0 fail | [hook](results/node-hook.txt) |
| python -m pip check | No broken requirements found | [pip](results/pip-check.txt) |
| openspec validate change --strict до кода | valid | [review](results/openspec-review.txt) |
| openspec archive search-saved-catalog --yes | 3 requirements синхронизированы, архив создан | [archive](results/openspec-archive.txt) |
| openspec validate --all --strict после archive | 1 spec passed, 0 failed | [final spec](results/openspec-final.txt) |

## Сквозные сценарии

В tests/test_sdd_features.py HTTP-клиент получает Jinja HTML, извлекает action/fields
настоящей формы через BeautifulSoup, вызывает HTTP, проверяет БД/API и результат HTML.
Каждая строка ниже реально проверена; ожидаемое совпало с фактическим, если указан PASS.

| Сценарий | Ввод/действия | Ожидается | Фактически / способ | Статус |
|---|---|---|---|---|
| Основной поиск | GET формы с `СЕМГА` по полным conditions | Только карточка «Бонус», счётчик 1, q сохранён | HTTP test_search_http_full_path: совпало | PASS |
| Реальные исторические акции | HTTP GET формы `КУПОН` | Совпадающие title/conditions, меньше полного каталога | Процессный smoke: 8 из 13 | PASS |
| Нормализация | СЁМГА, пробелы, полные\nусловия | Один результат без мутации входа | 3 parametrized tests | PASS |
| Нет совпадений | `нет совпадений`, `zzzzzzzz` | 0, специальное сообщение | TestClient и uvicorn: совпало | PASS |
| Пустой каталог | GET q=скидка на новой БД | Подсказка импорта, не сообщение о поиске | test_empty_catalog_search | PASS |
| Границы поиска | 100/101 букв, 150 пробелов | 100 разрешено; 101 ошибка и полный каталог; пробелы возвращают всё | unit + HTTP; role=alert, 200 | PASS |
| Экранирование | `<script>alert(1)</script>` | Ввод не исполняется, HTML escaped | HTTP: &lt;script&gt;, raw тега нет | PASS |
| Основная массовая отметка | HTML форма, 2 СПб + 1 Москва | 303, N=2, unread=0, Москва не меняется | test_read_city_http_full_path_and_search: совпало | PASS |
| Реальная история | Форма на snapshots | Только текущий город, история не удалена | uvicorn: 7 отмечено, 15 записей сохранено | PASS |
| Повтор/прочитанные | Повторный POST; одна карточка уже прочитана | N=0 при повторе; считать только новые | HTTP повтор 0; storage после индивидуальной отметки 1 | PASS |
| Пустой профиль/история | GET без города, POST с городом; сохранённый город без записей | disabled; ошибка; без записей N=0 | HTTP + SQL: совпало | PASS |
| Границы города | 100/101 символ, СПб и пробелы | 100 допустимо; 101 ошибка; алиас совпадает | SQL+HTTP: совпало | PASS |
| Устаревшая форма | Показана СПб, сохранена Москва, POST expected_city=СПб | Сообщение об изменении, без отметок | Полный state до/после одинаков | PASS |
| Пустой/отсутствующий Form | POST без поля или с пустым значением | 422 без записи по контракту 1.1 | Реальный первый FAIL привёл к уточнению, повтор PASS | PASS |
| Пробельный город | POST expected_city='   ' | Сообщение о сохранении города, 303 | HTTP, состояние неизменно | PASS |
| Чужой сайт/метод | Origin другой; GET mutating URL | 403 / 405, без записи | TestClient; Origin также uvicorn | PASS |
| Существующее поведение | Индивидуальная отметка, импорт, CLI/MCP, дедупликация, фон | Старые сценарии сохраняются | Все прежние 52 теста в общем suite | PASS |
| Взаимодействие фич | Поиск, массовая отметка, повтор поиска | Каталог не меняется, отметка не ограничена q | test_read_city_http_full_path_and_search | PASS |
| Персистентность | Новый TestClient и настоящий restart uvicorn | Прочтение сохраняется | Отдельный process-smoke: restart_persistence=true | PASS |

Сборка frontend отсутствует: Jinja рендерится сервером. Проверены AST всех Python,
импорт приложения и фактический запуск uvicorn. Онлайн-сбор и визуальное поведение
реального браузера не проверялись; TestClient не называется браузерным E2E.
Перезапуск процесса проверен отдельным script, не только lifecycle TestClient.

Первый baseline внутри sandbox не прошёл (MCP/зависание); после сравнения той же
команды вне sandbox все 52 теста прошли. Штатный skill tool systematic-debugging
недоступен; выполнены сбор свидетельств, сравнение, проверка гипотезы ограничений,
повтор вне sandbox. Исходную функциональность ради этого не меняли.
