"""Подбор уведомлений и обновление источника; read-only preview пригоден для MCP."""
import threading
from datetime import datetime
from app.domain import city_status,time_status,normalize_city,TZ
from app import storage
from app.source import collect_live,collect_snapshots

SYNC_LOCK=threading.Lock()


def preview_notifications(now=None,*,read_only=False):
    now=now or datetime.now(TZ)
    state=storage.read_state(read_only=read_only);city=state['city'];subs={n['key'] for n in state['networks'] if n['subscribed']}
    existing={(n['network'],n['source_id'],n['city_key'],n['content_hash']) for n in state['notifications']}
    selected=[];excluded=[]
    for p in state['promotions']:
        reason=None
        if p['network'] not in subs: reason='Нет подписки на сеть'
        elif not p['listed']: reason='Не найдена в последнем полном каталоге'
        elif city_status(p,city)!='applicable': reason='Территория не подходит или не подтверждена'
        elif time_status(p,now)!='active': reason='Акция не действует сейчас или сроки неизвестны'
        elif (p['network'],p['source_id'],normalize_city(city),p['content_hash']) in existing: reason='Уведомление уже создано'
        if reason: excluded.append({'network':p['network'],'source_id':p['source_id'],'reason':reason})
        else: selected.append(p)
    return {'city':city,'subscriptions':sorted(subs),'checked_at':now.isoformat(),
            'notifications':selected,'excluded':excluded}


def generate_notifications(now=None):
    preview=preview_notifications(now)
    return storage.add_notifications(preview['notifications'],preview['city'])


def synchronize(snapshot_dir=None,collector=None,now=None):
    if not SYNC_LOCK.acquire(blocking=False): return {'status':'busy','message':'Проверка уже выполняется'}
    try:
        try:
            collected=collector() if collector else (collect_snapshots(snapshot_dir) if snapshot_dir else collect_live())
            stats=storage.import_promotions(collected['promotions'],complete=collected['complete'])
            count=generate_notifications(now)
            result={'status':'ok' if collected['complete'] else 'partial','mode':collected['mode'],
                    'links_found':collected['links_found'],'fetched':len(collected['promotions']),
                    'errors':collected['errors'],'new_notifications':count,**stats}
        except Exception as exc:
            result={'status':'error','message':str(exc),'new_notifications':0}
        storage.record_sync(result)
        return result
    finally: SYNC_LOCK.release()
