"""Изолированное историческое демо и процессная HTTP-проверка лабораторной 5."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--smoke',action='store_true')
    args=parser.parse_args()
    directory=Path(tempfile.mkdtemp(prefix='lab05-'))
    os.environ.update(APP_DB_PATH=str(directory/'promos.db'),APP_BACKGROUND='0',
                      APP_SNAPSHOT_DIR=str(ROOT/'research/snapshots'))
    from app import storage
    from app.source import collect_snapshots
    from app.service import generate_notifications
    collected=collect_snapshots(ROOT/'research/snapshots')
    assert collected['complete'] and not collected['errors']
    storage.import_promotions(collected['promotions'],complete=True)
    storage.subscribe('rostics',True)
    now=datetime.fromisoformat('2026-10-07T12:00:00+03:00')
    for city in ('Москва','Санкт-Петербург'):
        storage.set_city(city);generate_notifications(now)
    print(f'Историческое демо на 07.10.2026; отдельная база: {directory}',flush=True)
    command=[sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port']
    if not args.smoke:
        os.chdir(ROOT)
        os.execv(sys.executable,[*command,'8000'])
    import httpx
    from bs4 import BeautifulSoup
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    with httpx.Client(base_url=f'http://127.0.0.1:{port}',timeout=3,follow_redirects=True) as client:
        def start():
            process=subprocess.Popen([*command,str(port)],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            try:
                for _ in range(100):
                    if process.poll() is not None: raise RuntimeError('uvicorn завершился до запуска')
                    try:
                        if client.get('/health').status_code==200: return process
                    except httpx.TransportError: pass
                    time.sleep(.1)
                raise RuntimeError('uvicorn не запустился за 10 секунд')
            except BaseException:
                process.terminate();process.wait(timeout=5);raise
        process=start()
        try:
            before=client.get('/api/state').json()
            soup=BeautifulSoup(client.get('/').text,'html.parser')
            all_count=len(soup.select('#catalog article'))
            search=soup.select_one('#catalog-query').find_parent('form')
            found=client.get(search['action'],params={'q':'КУПОН'})
            assert found.status_code==200
            found_count=len(BeautifulSoup(found.text,'html.parser').select('#catalog article'))
            assert 0<found_count<all_count
            assert 'По вашему запросу акции не найдены' in client.get('/',params={'q':'zzzzzzzz'}).text
            assert 'role="alert"' in client.get('/',params={'q':'а'*101}).text
            form=soup.select_one('form[action="/notifications/read-city"]')
            data={i['name']:i['value'] for i in form.select('input[name]')}
            response=client.post(form['action'],data=data)
            after=client.get('/api/state').json()
            current=[n for n in before['notifications'] if n['city']=='Санкт-Петербург']
            assert current and f'Отмечено прочитанными: {len(current)}' in response.text
            assert all(n['is_read'] for n in after['notifications'] if n['city']=='Санкт-Петербург')
            assert all(not n['is_read'] for n in after['notifications'] if n['city']=='Москва')
            assert len(before['notifications'])==len(after['notifications'])
            assert before['promotions']==after['promotions']
            assert 'Отмечено прочитанными: 0' in client.post(form['action'],data=data).text
            assert client.post(form['action'],data=data,headers={'origin':'https://other.example'}).status_code==403
        finally:
            process.terminate();process.wait(timeout=5)
        process=start()
        try: assert client.get('/api/state').json()==after
        finally: process.terminate();process.wait(timeout=5)
    print(json.dumps({'status':'PASS','catalog':all_count,'search_coupon':found_count,
                      'marked_current_city':len(current),'history':len(after['notifications']),
                      'restart_persistence':True,'cross_origin':403},ensure_ascii=False))


if __name__=='__main__': main()
