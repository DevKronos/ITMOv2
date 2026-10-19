"""Explicit offline preparation, separate from the MCP tool. Refuses existing DBs."""
import os
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    from app import storage
    from app.source import collect_snapshots
    if not os.environ.get('APP_DB_PATH'):
        raise SystemExit('Задайте APP_DB_PATH на новую демонстрационную базу')
    path=storage.database_path().resolve()
    if path==(ROOT/'data/promos.db').resolve() or path.exists():
        raise SystemExit('Нужна новая отдельная база; существующую и рабочую базу не изменяем')
    collected=collect_snapshots(ROOT/'research/snapshots')
    if not collected['complete'] or collected['errors']:
        raise SystemExit(f"Не удалось прочитать snapshots: {collected['errors']}")
    stats=storage.import_promotions(collected['promotions'],complete=True)
    storage.set_city('Санкт-Петербург')
    storage.subscribe('rostics',True)
    print(f'Исторические snapshots, без сети: {stats}; город Санкт-Петербург; подписка rostics; уведомления не создавались')


if __name__=='__main__': main()
