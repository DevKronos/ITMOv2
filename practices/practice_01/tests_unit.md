# Unit-проверки

Файл ведёт OpenCode. Обсудите с агентом содержание и проверьте предложенный diff. Все дополнения и исправления поручайте агенту в чате.

| Требование или правило | Что проверяем изолированно | Вход | Ожидаемый результат | Подтверждение |
|---|---|---|---|---|
| ReviewService.review формирует корректный промпт и возвращает словарь с ключом `comment` | Поведение `ReviewService.review()` со стабом LLM, без FastAPI | `diff = "some change"`; стаб LLM возвращает `"ok"` | В LLM передан промпт `"Review this pull request and find problems:\nsome change"`; результат функции — `{"comment": "ok"}` | `TRAINING_PR.diff` (app/review_service.py:19-22); `context.md` (факты о промпте и формате фактического ответа) |
| ReviewService.review включает diff в промпт без искажений (включая переходы строк) | Формирование строки промпта | `diff = "line1\nline2"`; стаб LLM возвращает `"r"` | В LLM передан промпт `"Review this pull request and find problems:\nline1\nline2"`; результат — `{"comment": "r"}` | `TRAINING_PR.diff` (app/review_service.py:20) |
| API create_review возвращает результат review_service.review | Поведение обработчика `create_review(payload: dict)` со стабом `review_service` | `payload = {"diff": "d"}`; стаб `review_service.review` возвращает `{ "comment": "x" }` | Возвращено `{ "comment": "x" }`; стаб вызван с аргументом `"d"` | `TRAINING_PR.diff` (app/api.py:35-38) |
| API create_review при отсутствии поля diff выбрасывает KeyError (AS IS) | Обработчик `create_review` при `payload = {}` | `payload = {}` | Поднимается `KeyError` при обращении `payload["diff"]` | `context.md` («Хороший пример» про KeyError), `TRAINING_PR.diff` (app/api.py:35-38) |
| Эндпоинт здоровья возвращает статус ok | Функция `health()` без внешних зависимостей | вызов `health()` | Возвращается `{"status": "ok"}` | `TRAINING_PR.diff` (app/api.py:40-42) |

## Как использовали AI

- Строка в [`prompts.md`](prompts.md): будет добавлена после записи задачи про unit‑проверки.
- Что проверил студент и какие исправления поручил агенту: утвердил проверку формирования промпта и возврата `{"comment": ...}` для AS IS, поведение при отсутствии `diff` (KeyError), корректность `health()` и прокидывание результата из `review_service` в обработчике API. Тесты для 413 и структурированного ответа отнесены к интеграционным/следующим инкрементам, так как формат ошибки не определён в контексте.
