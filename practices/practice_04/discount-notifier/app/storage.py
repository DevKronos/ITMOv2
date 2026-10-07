"""SQLite: один локальный пользователь, сети, акции, подписки и уведомления."""
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from app.domain import fingerprint, normalize_city

ROOT=Path(__file__).resolve().parent.parent
NETWORKS=[('rostics','Rostic’s',1),('vkusno','Вкусно — и точка',0),('burgerking','Бургер Кинг',0),('dodo','Додо Пицца',0)]


def now_iso(): return datetime.now(timezone.utc).isoformat()


def database_path(): return Path(os.environ.get('APP_DB_PATH',str(ROOT/'data/promos.db')))


@contextmanager
def connection():
    path=database_path();path.parent.mkdir(parents=True,exist_ok=True)
    conn=sqlite3.connect(path,timeout=15);conn.row_factory=sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA journal_mode=WAL')
    try:
        conn.executescript('''
        CREATE TABLE IF NOT EXISTS networks(key TEXT PRIMARY KEY,name TEXT NOT NULL,has_source INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS preferences(id INTEGER PRIMARY KEY CHECK(id=1),city TEXT NOT NULL DEFAULT '');
        CREATE TABLE IF NOT EXISTS subscriptions(network TEXT PRIMARY KEY REFERENCES networks(key));
        CREATE TABLE IF NOT EXISTS promotions(network TEXT NOT NULL REFERENCES networks(key),source_id TEXT NOT NULL,
            data TEXT NOT NULL,content_hash TEXT NOT NULL,retrieved_at TEXT NOT NULL,updated_at TEXT NOT NULL,
            listed INTEGER NOT NULL DEFAULT 1,PRIMARY KEY(network,source_id));
        CREATE TABLE IF NOT EXISTS notifications(id INTEGER PRIMARY KEY,network TEXT NOT NULL,source_id TEXT NOT NULL,
            city_key TEXT NOT NULL,city TEXT NOT NULL,content_hash TEXT NOT NULL,data TEXT NOT NULL,
            created_at TEXT NOT NULL,is_read INTEGER NOT NULL DEFAULT 0,
            UNIQUE(network,source_id,city_key,content_hash));
        CREATE TABLE IF NOT EXISTS sync_runs(id INTEGER PRIMARY KEY,created_at TEXT NOT NULL,result TEXT NOT NULL);
        ''')
        conn.executemany('INSERT OR IGNORE INTO networks VALUES(?,?,?)',NETWORKS)
        conn.execute("INSERT OR IGNORE INTO preferences(id,city) VALUES(1,'')")
        conn.commit()
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback();raise
    finally: conn.close()


def set_city(city):
    city=' '.join(city.split()).strip()
    if not city or len(city)>100: raise ValueError('Введите название города (до 100 символов)')
    with connection() as c: c.execute('UPDATE preferences SET city=? WHERE id=1',(city,))


def subscribe(network,enabled):
    with connection() as c:
        if not c.execute('SELECT 1 FROM networks WHERE key=?',(network,)).fetchone(): raise ValueError('Неизвестная сеть')
        if enabled: c.execute('INSERT OR IGNORE INTO subscriptions VALUES(?)',(network,))
        else: c.execute('DELETE FROM subscriptions WHERE network=?',(network,))


@contextmanager
def readonly_connection():
    """Strictly read a quiescent database; never create/update even WAL/SHM files.

    immutable skips SQLite sidecar writes, but also ignores WAL. Refuse WAL rather
    than silently return old data. Caller must use a dedicated, inactive database.
    Normal web/CLI connections keep their existing WAL behaviour.
    """
    path=database_path().resolve()
    if not path.is_file():
        raise FileNotFoundError('База не существует; подготовьте её отдельно через приложение или CLI')
    if Path(str(path)+'-wal').exists():
        raise ValueError('База имеет WAL: для строгого предпросмотра используйте отдельную базу '
                         'без активных писателей после их штатного закрытия; WAL не удаляйте вручную')
    conn=sqlite3.connect(path.as_uri()+'?mode=ro&immutable=1',uri=True,timeout=15)
    conn.row_factory=sqlite3.Row
    try:
        conn.execute('PRAGMA query_only=ON')
        conn.execute('BEGIN')  # All SELECTs see one consistent snapshot.
        yield conn
        if Path(str(path)+'-wal').exists():
            raise ValueError('База изменяется другим процессом; повторите с отдельной неактивной базой')
    finally:
        conn.close()


def read_state(*,read_only=False):
    with (readonly_connection() if read_only else connection()) as c:
        preference=c.execute('SELECT city FROM preferences WHERE id=1').fetchone()
        if preference is None: raise ValueError('База не подготовлена: отсутствует локальный профиль')
        city=preference[0]
        networks=[dict(r) for r in c.execute('SELECT n.*,s.network IS NOT NULL AS subscribed FROM networks n LEFT JOIN subscriptions s ON n.key=s.network ORDER BY has_source DESC,name')]
        promos=[]
        for r in c.execute('SELECT * FROM promotions ORDER BY network,source_id'):
            p=json.loads(r['data']);p.update(listed=bool(r['listed']),updated_at=r['updated_at'],content_hash=r['content_hash']);promos.append(p)
        notes=[dict(r) for r in c.execute('SELECT * FROM notifications ORDER BY id DESC')]
        for n in notes: n['promotion']=json.loads(n.pop('data'))
        last=c.execute('SELECT result,created_at FROM sync_runs ORDER BY id DESC LIMIT 1').fetchone()
    return {'city':city,'networks':networks,'promotions':promos,'notifications':notes,'last_sync':({'created_at':last['created_at'],**json.loads(last['result'])} if last else None)}


def validate_promo(p):
    for key in ('network','source_id','source_url','title','conditions','retrieved_at'):
        if not isinstance(p.get(key),str) or not p[key].strip(): raise ValueError(f'Не заполнено поле {key}')
    if p['network'] not in {n[0] for n in NETWORKS}: raise ValueError('Неизвестная сеть акции')
    parsed=datetime.fromisoformat(p['retrieved_at'])
    if parsed.tzinfo is None: raise ValueError('retrieved_at требует часовой пояс')
    if not isinstance(p.get('geography'),dict): raise ValueError('Нет структуры geography')


def import_promotions(promotions,complete=False,network='rostics'):
    """Атомарный upsert. complete=True только для полного успешного каталога."""
    seen=set();inserted=updated=unchanged=0;now=now_iso()
    with connection() as c:
        for p in promotions:
            validate_promo(p)
            key=(p['network'],p['source_id'])
            if key in seen: raise ValueError('Повтор ID в одном импорте')
            seen.add(key);hash_=fingerprint(p)
            previous=c.execute('SELECT content_hash,updated_at FROM promotions WHERE network=? AND source_id=?',key).fetchone()
            if previous:
                stamp=now if previous['content_hash']!=hash_ else previous['updated_at']
                if previous['content_hash']!=hash_: updated+=1
                else: unchanged+=1
            else: stamp=now;inserted+=1
            c.execute('''INSERT INTO promotions VALUES(?,?,?,?,?,?,1)
                ON CONFLICT(network,source_id) DO UPDATE SET data=excluded.data,content_hash=excluded.content_hash,
                retrieved_at=excluded.retrieved_at,updated_at=excluded.updated_at,listed=1''',
                (*key,json.dumps(p,ensure_ascii=False),hash_,p['retrieved_at'],stamp))
        if complete:
            # Отсутствие в полном каталоге не означает истечение срока; отдельная метка.
            for r in c.execute('SELECT source_id FROM promotions WHERE network=?',(network,)).fetchall():
                if (network,r['source_id']) not in seen:
                    c.execute('UPDATE promotions SET listed=0 WHERE network=? AND source_id=?',(network,r['source_id']))
    return {'inserted':inserted,'updated':updated,'unchanged':unchanged}


def add_notifications(candidates,city):
    count=0
    with connection() as c:
        # Перепроверка настроек защищает от смены города/отписки между подбором и записью.
        if normalize_city(c.execute('SELECT city FROM preferences WHERE id=1').fetchone()[0])!=normalize_city(city): return 0
        subscribed={r[0] for r in c.execute('SELECT network FROM subscriptions')}
        for p in candidates:
            if p['network'] not in subscribed: continue
            cur=c.execute('''INSERT OR IGNORE INTO notifications(network,source_id,city_key,city,content_hash,data,created_at)
                VALUES(?,?,?,?,?,?,?)''',(p['network'],p['source_id'],normalize_city(city),city,p['content_hash'],json.dumps(p,ensure_ascii=False),now_iso()))
            count+=cur.rowcount
    return count


def mark_read(notification_id):
    with connection() as c:
        return bool(c.execute('UPDATE notifications SET is_read=1 WHERE id=?',(notification_id,)).rowcount)


def record_sync(result):
    with connection() as c: c.execute('INSERT INTO sync_runs(created_at,result) VALUES(?,?)',(now_iso(),json.dumps(result,ensure_ascii=False)))
