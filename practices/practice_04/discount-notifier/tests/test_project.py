import copy
import hashlib
import json
import threading
from datetime import datetime
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app import storage
from app.domain import parse_dates,time_status,city_status,geography,TZ
from app.source import catalog_links,parse_promo,collect_snapshots,collect_live,SourceError
from app.service import generate_notifications,preview_notifications,synchronize
from app.main import app,background_loop

SNAP=Path(__file__).resolve().parents[1]/'research/snapshots'
NOW=datetime(2026,10,7,12,tzinfo=TZ)


@pytest.mark.parametrize('text,expected',[
 ('с 24 сентября по 8 октября 2026 года',('2026-09-24','2026-10-08')),
 ('с 3 по 31 августа 2026 года',('2026-08-03','2026-08-31')),
 ('с 15 июня 2026 года по 31 декабря 2026 года',('2026-06-15','2026-12-31')),
 ('03.09.2026 по 02.11.2026',('2026-09-03','2026-11-02')),
 ('C 1.10.2026 г. по 31.10.2026 г.',('2026-10-01','2026-10-31')),
 ('31.02.2026 — 31.12.2026',(None,None)),
 ('с 30 октября по 1 октября 2026 года',(None,None)),
 ('Пока товар есть в наличии',(None,None)),
])
def test_dates(text,expected): assert parse_dates(text)==expected


@pytest.mark.parametrize('day,status',[('2026-09-30','future'),('2026-10-31','active'),('2026-11-01','ended')])
def test_boundaries(promo,day,status): assert time_status(promo,datetime.fromisoformat(day).replace(tzinfo=TZ))==status


def test_timezone_and_weekdays(promo):
    promo['weekdays']=[4,5,6]
    assert time_status(promo,NOW)=='off_day'
    assert time_status(promo,datetime.fromisoformat('2026-10-09T00:00:00+03:00'))=='active'
    assert time_status(promo,datetime.fromisoformat('2026-10-31T22:00:00+00:00'))=='ended'
    with pytest.raises(ValueError): time_status(promo,datetime(2026,10,7))


def test_city_matching_and_unknown(promo):
    promo['geography']=geography('', ['Ресторан Томск, г. Томск, ул. Ленина'])
    assert city_status(promo,'Томск')=='applicable'
    assert city_status(promo,'Омск')=='not_applicable'
    promo['geography']=geography('', ['Неизвестный формат адреса'])
    assert city_status(promo,'Омск')=='unknown'
    assert city_status(promo,'')=='unknown'


def test_exceptions_paragraph(promo):
    promo['geography']=geography('Акция по всей России, кроме городов-исключений: Артем, Якутск\nПредложение не суммируется с купонами, промокодами.',[])
    assert promo['geography']['excluded_cities']==['Артем','Якутск']
    assert city_status(promo,' Якутск ')=='not_applicable'
    assert city_status(promo,'Санкт-Петербург')=='applicable'
    assert city_status(promo,None)=='unknown'


def test_real_catalog_and_parser():
    result=collect_snapshots(SNAP)
    assert result['complete'] and not result['errors'] and len(result['promotions'])==13
    by_id={p['source_id']:p for p in result['promotions']}
    snack=by_id['snack20frombskt']
    assert len(snack['participating_locations'])==153
    assert all('Вакансии' not in l for l in snack['participating_locations'])
    assert '"Баскеты"' in snack['conditions'] and '&quot;' not in snack['conditions']
    assert city_status(snack,'Санкт-Петербург')=='not_applicable'
    assert time_status(by_id['dishfrom1799'],NOW)=='ended'
    assert city_status(by_id['dish1rub700'],'Якутск')=='not_applicable'
    assert city_status(by_id['dish1rub700'],'Санкт-Петербург')=='applicable'
    assert 'купонами' not in by_id['dish1rub700']['geography']['excluded_cities']
    assert time_status(by_id['bsk15'],NOW)=='off_day'
    assert by_id['thosewhorule']['starts_on']=='2026-10-01'


def test_error_pages_and_empty_catalog():
    for html in ['<h1>Access denied</h1>','<h1>Новая разметка</h1>','<h1>Акции</h1>']:
        with pytest.raises(SourceError): catalog_links(html)
    with pytest.raises(SourceError): parse_promo('<h1>Access denied</h1>','https://rostics.ru/promo/test')


def test_partial_collection_keeps_successes():
    catalog=(SNAP/'https_rostics_ru_promo.html').read_text()
    def fake(url):
        if url.endswith('/promo'): return catalog
        if url.endswith('/snack20frombskt'): return (SNAP/'https_rostics_ru_promo_snack20frombskt.html').read_text()
        raise SourceError('Временная ошибка')
    result=collect_live(fake)
    assert len(result['promotions'])==1 and len(result['errors'])==12 and not result['complete']


def test_import_idempotence_and_content_change(promo):
    assert storage.import_promotions([promo])['inserted']==1
    before=storage.read_state()['promotions'][0]
    promo['retrieved_at']='2026-10-08T00:00:00+00:00'
    assert storage.import_promotions([promo])['unchanged']==1
    after=storage.read_state()['promotions'][0]
    assert before['updated_at']==after['updated_at'] and before['content_hash']==after['content_hash']
    promo['conditions']='Изменённые условия'
    assert storage.import_promotions([promo])['updated']==1
    assert len(storage.read_state()['promotions'])==1
    assert storage.read_state()['promotions'][0]['content_hash']!=before['content_hash']


def test_import_rollback(promo):
    bad=copy.deepcopy(promo);bad['source_id']='second';bad['title']=''
    with pytest.raises(ValueError): storage.import_promotions([promo,bad])
    assert storage.read_state()['promotions']==[]


def test_city_persistence_and_subscription_idempotence():
    assert storage.read_state()['city']==''
    storage.set_city('Санкт-Петербург');storage.subscribe('rostics',True);storage.subscribe('rostics',True)
    state=storage.read_state();assert state['city']=='Санкт-Петербург'
    assert sum(n['subscribed'] for n in state['networks'])==1
    storage.subscribe('rostics',False);assert not any(n['subscribed'] for n in storage.read_state()['networks'])
    with pytest.raises(ValueError):storage.subscribe('unknown',True)
    with pytest.raises(ValueError):storage.set_city(' ')


def test_preview_notifications_and_dedup(promo):
    storage.import_promotions([promo]);storage.set_city('Санкт-Петербург')
    assert generate_notifications(NOW)==0
    storage.subscribe('rostics',True)
    assert len(preview_notifications(NOW)['notifications'])==1
    assert not storage.read_state()['notifications'] # preview не пишет уведомления
    assert generate_notifications(NOW)==1
    assert generate_notifications(NOW)==0
    note=storage.read_state()['notifications'][0];assert storage.mark_read(note['id'])
    assert storage.read_state()['notifications'][0]['is_read']==1
    storage.set_city('Якутск');assert generate_notifications(NOW)==0
    storage.set_city('Москва');assert generate_notifications(NOW)==1
    storage.subscribe('rostics',False)
    promo['conditions']='Новое предложение';storage.import_promotions([promo])
    assert generate_notifications(NOW)==0


def test_unknown_ended_and_offday_do_not_notify(promo):
    storage.set_city('Москва');storage.subscribe('rostics',True)
    for change in [{'ends_on':'2026-10-01'},{'geography':{'kind':'unknown'}},{'starts_on':None},{'weekdays':[4]}]:
        p={**promo,**change};storage.import_promotions([p]);assert generate_notifications(NOW)==0


def test_sync_error_preserves_data_and_partial_does_not_hide(promo):
    storage.import_promotions([promo])
    def fail(): raise SourceError('403')
    assert synchronize(collector=fail)['status']=='error'
    assert storage.read_state()['promotions'][0]['listed']
    result=synchronize(collector=lambda:{'promotions':[],'complete':False,'errors':[{'error':'oops'}],'links_found':1,'mode':'live'})
    assert result['status']=='partial' and storage.read_state()['promotions'][0]['listed']
    storage.import_promotions([],complete=True)
    assert not storage.read_state()['promotions'][0]['listed']


def test_background_runs_without_button():
    stop=threading.Event();called=threading.Event()
    def run(): called.set();stop.set()
    thread=threading.Thread(target=background_loop,args=(stop,.01,run));thread.start()
    assert called.wait(1);thread.join(1);assert not thread.is_alive()


def test_http_routes_and_isolation(promo):
    with TestClient(app) as client:
        assert client.get('/health').json()=={'status':'ok'}
        assert client.get('/').status_code==200
        assert client.post('/city',data={'city':'Москва'},follow_redirects=False).status_code==303
        assert client.post('/subscriptions/rostics',data={'enabled':1}).status_code==200
        assert client.get('/api/state').json()['city']=='Москва'
        assert client.post('/city',data={'city':'Москва'},headers={'Origin':'https://example.com'}).status_code==403
        assert client.post('/subscriptions/nope',data={'enabled':1}).status_code==404
        assert client.post('/notifications/999/read').status_code==404
        storage.import_promotions([promo])
        page=client.get('/').text
        assert 'Подходит по территории' in page and 'Сроки не подтверждены' not in page
        promo['ends_on']=None;storage.import_promotions([promo])
        assert 'Сроки не подтверждены' in client.get('/').text


def test_background_sync_creates_notification(promo):
    storage.set_city('Санкт-Петербург');storage.subscribe('rostics',True)
    stop=threading.Event();done=threading.Event();results=[]
    def collector():return {'promotions':[promo],'complete':True,'errors':[],'links_found':1,'mode':'test'}
    def run():
        results.append(synchronize(collector=collector,now=NOW));done.set();stop.set()
    thread=threading.Thread(target=background_loop,args=(stop,.01,run));thread.start()
    try:
        assert done.wait(2)
        assert results[0]['new_notifications']==1
        assert len(storage.read_state()['notifications'])==1
    finally:stop.set();thread.join(2)


def test_concurrent_sync_is_not_started():
    from app.service import SYNC_LOCK
    SYNC_LOCK.acquire()
    try:
        def should_not_run():raise AssertionError('Сборщик не должен запускаться')
        assert synchronize(collector=should_not_run)['status']=='busy'
    finally:SYNC_LOCK.release()


def test_snapshot_http_workflow_and_restart(monkeypatch):
    import app.main as web
    monkeypatch.setattr(web,'generate_notifications',lambda:generate_notifications(NOW))
    collected=collect_snapshots(SNAP)
    assert storage.import_promotions(collected['promotions'],complete=True)=={'inserted':13,'updated':0,'unchanged':0}
    assert storage.import_promotions(collected['promotions'],complete=True)=={'inserted':0,'updated':0,'unchanged':13}
    with TestClient(app) as client:
        assert client.post('/city',data={'city':'Санкт-Петербург'}).status_code==200
        assert client.post('/subscriptions/rostics',data={'enabled':1}).status_code==200
        assert client.post('/notifications/check').status_code==200
        notes=client.get('/api/state').json()['notifications']
        assert len(notes)==7
        assert client.post('/notifications/check').status_code==200
        assert len(client.get('/api/state').json()['notifications'])==7
        assert client.post(f"/notifications/{notes[0]['id']}/read").status_code==200
    with TestClient(app) as client:
        state=client.get('/api/state').json()
        assert state['city']=='Санкт-Петербург'
        assert next(n for n in state['networks'] if n['key']=='rostics')['subscribed']
        assert len(state['notifications'])==7
        assert sum(n['is_read'] for n in state['notifications'])==1


def test_lifespan_background_collects_and_deduplicates(promo,monkeypatch):
    import app.main as web
    import app.service as service
    storage.set_city('Москва');storage.subscribe('rostics',True)
    monkeypatch.setenv('APP_BACKGROUND','1')
    done=threading.Event();results=[];calls=[]
    def collector():
        calls.append(threading.get_ident())
        return {'promotions':[promo],'complete':True,'errors':[],'links_found':1,'mode':'test'}
    monkeypatch.setattr(service,'collect_live',collector)
    def sync(directory):
        results.append(synchronize(directory,now=NOW))
        if len(results)==2: done.set()
    monkeypatch.setattr(web,'synchronize',sync)
    def accelerated_loop(stop,interval,runner):
        assert interval==1800
        def tick():
            runner()
            if done.is_set(): stop.set()
        background_loop(stop,.01,tick)
    monkeypatch.setenv('APP_SYNC_INTERVAL','1800')
    monkeypatch.setattr(web,'background_loop',accelerated_loop)
    with TestClient(app):
        assert done.wait(3)
        assert [r['new_notifications'] for r in results]==[1,0]
        assert len(calls)==2 and all(t!=threading.get_ident() for t in calls)
        assert len(storage.read_state()['notifications'])==1
