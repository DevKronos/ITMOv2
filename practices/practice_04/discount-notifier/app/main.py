import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI,Form,HTTPException,Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app import storage
from app.domain import city_status,time_status,normalize_city
from app.service import synchronize,generate_notifications,preview_notifications

ROOT=Path(__file__).resolve().parent
TERRITORY={'applicable':'Подходит по территории','not_applicable':'Другой город','unknown':'Территория не подтверждена'}
TIME={'active':'В периоде действия','ended':'Завершилась','future':'Ещё не началась','off_day':'Сегодня не действует','unknown':'Сроки не подтверждены'}


def background_loop(stop,interval,runner):
    while not stop.wait(interval):
        runner()


@asynccontextmanager
async def lifespan(app):
    with storage.connection(): pass
    stop=threading.Event()
    enabled=os.environ.get('APP_BACKGROUND','1')=='1'
    interval=max(60,int(os.environ.get('APP_SYNC_INTERVAL','1800')))
    app.state.interval=interval;app.state.background=enabled
    if enabled:
        thread=threading.Thread(target=background_loop,args=(stop,interval,lambda:synchronize(os.environ.get('APP_SNAPSHOT_DIR') or None)),daemon=True)
        thread.start()
    try: yield
    finally: stop.set()


app=FastAPI(title='Акции рядом',lifespan=lifespan)
app.mount('/static',StaticFiles(directory=ROOT/'static'),name='static')
templates=Jinja2Templates(directory=ROOT/'templates')


@app.middleware('http')
async def same_origin_mutations(request:Request,call_next):
    # Локальный сервис без регистрации: не принимаем команды от сторонних сайтов.
    origin=request.headers.get('origin')
    if request.method=='POST' and origin and origin.rstrip('/')!=str(request.base_url).rstrip('/'):
        from fastapi.responses import JSONResponse
        return JSONResponse({'detail':'Запрос с другого сайта отклонён'},status_code=403)
    return await call_next(request)


@app.get('/')
def index(request:Request):
    state=storage.read_state()
    for p in state['promotions']:
        p['territory_label']=TERRITORY[city_status(p,state['city'])]
        p['time_label']=TIME[time_status(p)]
    networks={n['key']:n['name'] for n in state['networks']}
    unread=sum(not n['is_read'] and n['city_key']==normalize_city(state['city']) for n in state['notifications'])
    return templates.TemplateResponse(request=request,name='index.html',context={**state,'network_names':networks,'unread':unread,'background':getattr(app.state,'background',False),'interval':getattr(app.state,'interval',1800),'message':request.query_params.get('message','')})


def back(message=''):
    from urllib.parse import urlencode
    return RedirectResponse('/?'+urlencode({'message':message}) if message else '/',status_code=303)


@app.post('/city')
def city(city:str=Form(...)):
    try: storage.set_city(city)
    except ValueError as exc: return back(str(exc))
    return back('Город сохранён. Он учитывается при следующей проверке уведомлений.')


@app.post('/subscriptions/{network}')
def subscription(network:str,enabled:int=Form(...)):
    try: storage.subscribe(network,bool(enabled))
    except ValueError as exc: raise HTTPException(404,str(exc))
    return back('Подписка сохранена' if enabled else 'Подписка отменена')


@app.post('/sync')
def sync():
    result=synchronize(os.environ.get('APP_SNAPSHOT_DIR') or None)
    label={'ok':'Проверка завершена','partial':'Сбор выполнен частично: см. ошибки ниже','error':'Источник не удалось обновить','busy':'Проверка уже выполняется'}[result['status']]
    return back(f"{label}. Новых уведомлений: {result.get('new_notifications',0)}")


@app.post('/notifications/check')
def check_notifications(): return back(f'Создано уведомлений: {generate_notifications()}')


@app.post('/notifications/{notification_id}/read')
def read(notification_id:int):
    if not storage.mark_read(notification_id): raise HTTPException(404,'Уведомление не найдено')
    return back()


@app.get('/api/state')
def api_state(): return storage.read_state()


@app.get('/api/notifications/preview')
def api_preview(): return preview_notifications()


@app.get('/health')
def health(): return {'status':'ok'}
