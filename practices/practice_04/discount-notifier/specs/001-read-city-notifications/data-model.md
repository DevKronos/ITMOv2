# Данные и переходы
Миграции нет. preferences: id=1, city:str; notifications: id:int, city_key:str,
is_read:int 0|1, неизменяемые promotion/city/hash/created_at.
Команда: expected_city:str, непустая строка длиной <=100 до нормализации.
Результат: int>=0, только число переходов is_read 0→1 выбранного города.
Ограничение: normalize_city(expected_city)==normalize_city(preferences.city) != ''.
При несовпадении нет переходов; уже прочитанные 1→1 не считаются.
Смена города и эта команда сериализуются SQLite BEGIN IMMEDIATE.
