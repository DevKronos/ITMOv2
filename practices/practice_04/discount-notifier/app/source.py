"""ROSTIC’S: каталог и страницы из обычного HTML, без браузера и обхода защиты."""
import json
import errno
import re
import socket
import time
from datetime import datetime, timezone
from http.client import HTTPException, IncompleteRead, RemoteDisconnected
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from bs4 import BeautifulSoup
from app.domain import parse_dates, weekday_rule, geography

CATALOG='https://rostics.ru/promo'


class SourceError(RuntimeError):
    pass


def soup_for(html):
    soup=BeautifulSoup(html,'html.parser')
    heading=soup.find('h1')
    if heading and re.search(r'access denied|доступ запрещ|captcha|проверка доступа',heading.get_text(),re.I):
        raise SourceError('Получена техническая страница вместо акций')
    return soup


def catalog_links(html):
    soup=soup_for(html)
    h1=soup.find('h1')
    if not h1 or h1.get_text(strip=True)!='Акции': raise SourceError('Неизвестная разметка каталога')
    links=sorted({urljoin(CATALOG,a['href']) for a in soup.select('a[href]') if re.fullmatch(r'/promo/[a-zA-Z0-9_-]+/?',a['href'])})
    if not links: raise SourceError('Каталог без распознанных ссылок: пустота не подтверждена')
    return links


def parse_promo(html,url,retrieved_at=None):
    if urlparse(url).hostname!='rostics.ru' or not re.fullmatch(r'/promo/[a-zA-Z0-9_-]+/?',urlparse(url).path):
        raise SourceError('Ожидалась ссылка на официальную страницу акции ROSTIC’S')
    soup=soup_for(html);h1=soup.find('h1')
    if not h1 or h1.get_text(strip=True)=='Акции': raise SourceError('Нет заголовка конкретной акции')
    # Содержимое в блоке рядом с H1; не скрипты и не футер сайта.
    block=next((sibling for sibling in h1.find_next_siblings('div') if sibling.find('p')),None)
    if block is None or not block.find('p'): raise SourceError('Не распознан блок условий акции')
    conditions=[];locations=[];locations_header=None
    for p in block.find_all('p'):
        text=p.get_text(' ',strip=True)
        if re.search('Рестораны[‑-]участники акции',text,re.I): locations_header=p;break
        if text: conditions.append(text)
    if locations_header:
        ul=locations_header.find_next_sibling('ul')
        if ul is None: raise SourceError('Найден заголовок участников, но список не распознан')
        locations=[li.get_text(' ',strip=True) for li in ul.find_all('li',recursive=False)]
        if not locations: raise SourceError('Пустой список участников не подтверждён')
    text='\n'.join(conditions)
    if len(text)<30: raise SourceError('Недостаточно данных об условиях акции')
    start,end=parse_dates(text)
    period='\n'.join(p for p in conditions if re.search(r'\b(?:срок|период|проводится|действует)\b',p,re.I))
    discount=re.search(r'(?:скидк[аиу]\s+\d+\s*[%₽]|\d+\s*%\s*(?:скидк[аиу])?)',h1.get_text(' ',strip=True)+' '+text,re.I)
    return {'network':'rostics','source_id':urlparse(url).path.rstrip('/').split('/')[-1], 'source_url':url,'title':h1.get_text(' ',strip=True), 'conditions':text,'discount_text':discount.group(0) if discount else None,'period_text':period or None,'starts_on':start,'ends_on':end,'weekdays':weekday_rule(text),'participating_locations':locations,'geography':geography(text,locations),'retrieved_at':retrieved_at or datetime.now(timezone.utc).isoformat()}


def temporary_fetch_error(exc):
    if isinstance(exc,HTTPError): return exc.code in (408,500,502,503,504)
    reason=exc.reason if isinstance(exc,URLError) else exc
    if isinstance(reason,(TimeoutError,ConnectionResetError,ConnectionAbortedError,IncompleteRead,RemoteDisconnected)):
        return True
    if isinstance(reason,socket.gaierror): return reason.errno==socket.EAI_AGAIN
    return isinstance(reason,OSError) and reason.errno in (errno.ETIMEDOUT,errno.ECONNRESET,errno.ECONNABORTED)


def fetch_html(url,*,transport=None,wait=None):
    transport=transport or urlopen;wait=wait or time.sleep
    for attempt in range(1,4):
        stage='открытие соединения / TLS / ожидание заголовков'
        try:
            req=Request(url,headers={'User-Agent':'DiscountNotifier-Educational/1.0','Accept':'text/html'})
            with transport(req,timeout=20) as response:
                if response.status!=200:
                    raise HTTPError(url,response.status,'HTTP error',response.headers,None)
                if urlparse(response.url).hostname!='rostics.ru': raise SourceError('Редирект за пределы источника')
                stage='чтение ответа'
                body=response.read(5_000_001)
                if len(body)>5_000_000: raise SourceError('Ответ превышает лимит 5000000 байт')
                stage='декодирование ответа'
                return body.decode('utf-8')
        except (OSError,HTTPException,SourceError,UnicodeError) as exc:
            retry=temporary_fetch_error(exc)
            reason=exc.reason if isinstance(exc,URLError) else exc
            detail=f'HTTP {exc.code}' if isinstance(exc,HTTPError) else f'{type(reason).__name__}: {reason}'
            if isinstance(exc,HTTPError): exc.close()
            if not retry or attempt==3:
                raise SourceError(f'{url}: {detail}; этап: {stage}; попыток: {attempt}') from exc
            wait(.5*attempt)


def collect_live(fetch=fetch_html):
    links=catalog_links(fetch(CATALOG));promos=[];errors=[]
    for url in links:
        try: promos.append(parse_promo(fetch(url),url))
        except Exception as exc: errors.append({'url':url,'error':str(exc)})
        if fetch is fetch_html: time.sleep(.25)
    return {'promotions':promos,'errors':errors,'complete':not errors,'links_found':len(links),'mode':'live'}


def collect_snapshots(directory):
    directory=Path(directory)
    meta=[json.loads(p.read_text(encoding='utf-8')) for p in sorted(directory.glob('*.meta.json'))]
    by_url={m['url']:m for m in meta}
    cat=by_url.get(CATALOG)
    if not cat or cat.get('status')!=200: raise SourceError('Нет успешного snapshot каталога')
    links=catalog_links((directory/cat['file']).read_text(encoding='utf-8'));promos=[];errors=[]
    for url in links:
        try:
            m=by_url[url]
            if m.get('status')!=200: raise SourceError(f"Snapshot HTTP {m.get('status')}")
            name=Path(m['file'])
            if name.name!=str(name): raise SourceError('Некорректное имя snapshot')
            promos.append(parse_promo((directory/name).read_text(encoding='utf-8'),url,m['retrieved_at']))
        except Exception as exc: errors.append({'url':url,'error':str(exc)})
    return {'promotions':promos,'errors':errors,'complete':not errors,'links_found':len(links),'mode':'snapshots'}
