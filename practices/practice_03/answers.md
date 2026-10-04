# Эталоны по demo/

1. Как запустить тесты?
- Ответ: через make — команда "make test" вызывает "python3 -m unittest -v".
- Источник: demo/Makefile:1-3
```
.PHONY: test
test:
	python3 -m unittest -v
```
- Дополнение: README указывает использовать make test.
- Источник: demo/README.md:6
```
Проверка: make test.
```

2. Что будет при пустом имени подписчика?
- Ответ: будет выброшено исключение ValueError("empty name").
- Источник (проверка в функции): demo/service.py:5-6
```
if not name.strip():
    raise ValueError("empty name")
```
- Источник (подтверждающий тест): demo/test_service.py:13-15
```
def test_empty(self):
    with self.assertRaises(ValueError):
        subscribe(" ")
```

3. Где реализован unsubscribe?
- Ответ: в demo/ функция unsubscribe не реализована.
- Подтверждение:
  - В service.py есть только subscribers и subscribe, unsubscribe отсутствует.
    Источник: demo/service.py:1-8
  - Тесты покрывают только subscribe и поведение множества, unsubscribe не упоминается.
    Источник: demo/test_service.py:2, 9-21
```
from service import subscribe, subscribers
...
def test_subscribe(...); def test_empty(...); def test_duplicate(...)
```
  - В README описана только subscribe.
    Источник: demo/README.md:3-4
```
В service.py функция subscribe добавляет непустое имя в множество.
Повторное добавление имени не создаёт дубликат.
```

4. Какая CI-система запускает тесты?
- Ответ: сведений о CI нет в demo/.
- Подтверждение:
  - В demo/ отсутствуют конфигурации CI (нет .github/workflows/*, .gitlab-ci.yml и т.п.); среди файлов только Makefile, README.md, opencode.json, service.py, test_service.py, repo-system.txt.
  - Файл opencode.json описывает локальные агенты/модели, не CI.
    Источник: demo/opencode.json:29-63

5. Сохраняются ли подписки после перезапуска процесса?
- Ответ: нет, подписки хранятся только в памяти процесса и не переживают перезапуск.
- Подтверждение:
  - README прямо указывает хранение "в памяти процесса".
    Источник: demo/README.md:2
```
Подписчики хранятся в памяти процесса.
```
  - Реализация — глобальное множество без файлов/БД.
    Источник: demo/service.py:1
```
subscribers = set()
```
  - Отсутствует код сохранения/загрузки состояния (нет I/O, БД, сериализации) в service.py:1-8.
