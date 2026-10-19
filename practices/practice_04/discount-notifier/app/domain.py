"""Чистые правила сроков и географии; используются приложением и будущим MCP."""
import hashlib
import json
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo('Europe/Moscow')
MONTHS = dict(zip('января февраля марта апреля мая июня июля августа сентября октября ноября декабря'.split(), range(1, 13)))
WEEKDAYS = {'понедельник': 0, 'вторник': 1, 'сред': 2, 'четверг': 3, 'пятниц': 4, 'суббот': 5, 'воскресень': 6}


def normalize_city(value):
    value = re.sub(r'^\s*г\.?\s+', '', value or '', flags=re.I)
    value = re.sub(r'\s+', ' ', value.strip().casefold().replace('ё', 'е')).replace('‑', '-').replace('–', '-')
    return {'спб': 'санкт-петербург', 'с.-петербург': 'санкт-петербург', 'санкт петербург': 'санкт-петербург'}.get(value, value)


def parse_dates(text):
    """ISO-границы; никогда не додумывает год при переходе через Новый год."""
    t = (text or '').casefold()
    numeric = re.search(r'(?<!\d)(\d{1,2})\.(\d{1,2})\.(\d{4})\s*(?:г\.?\s*)?(?:по|—|–|-|до)\s*(\d{1,2})\.(\d{1,2})\.(\d{4})(?!\d)', t)
    # Числовые даты иногда разделены словами «включительно ... по».
    if not numeric:
        numeric = re.search(r'(\d{1,2})\.(\d{1,2})\.(\d{4})[^\n]{0,40}?\bпо\s+(\d{1,2})\.(\d{1,2})\.(\d{4})', t)
    names = '|'.join(MONTHS)
    full = re.search(rf'\bс\s+(\d{{1,2}})\s+({names})\s+(\d{{4}})(?:\s+года?|\s+г\.)?\s+по\s+(\d{{1,2}})\s+({names})\s+(\d{{4}})', t)
    shared = re.search(rf'\bс\s+(\d{{1,2}})(?:\s+({names}))?\s+по\s+(\d{{1,2}})\s+({names})\s+(\d{{4}})', t)
    try:
        if numeric:
            d1,m1,y1,d2,m2,y2 = map(int, numeric.groups())
        elif full:
            d1,m1,y1,d2,m2,y2 = full.groups(); m1,m2 = MONTHS[m1],MONTHS[m2]
        elif shared:
            d1,m1,d2,m2,y1 = shared.groups(); y2=y1; m1,m2=MONTHS[m1 or m2],MONTHS[m2]
        else:
            return None, None
        start,end = date(int(y1),int(m1),int(d1)), date(int(y2),int(m2),int(d2))
        return (start.isoformat(),end.isoformat()) if start <= end else (None,None)
    except (ValueError,KeyError,TypeError):
        return None,None


def weekday_rule(text):
    t = (text or '').casefold()
    m = re.search(r'с кажд\w*\s+([а-я]+)\s+по кажд\w*\s+([а-я]+)', t)
    def number(word):
        return next((n for stem,n in WEEKDAYS.items() if word.startswith(stem)), None)
    if m:
        a,b = map(number, m.groups())
        if a is not None and b is not None:
            return [(a+i)%7 for i in range((b-a)%7+1)]
    return []


def time_status(promo, now=None):
    now = now or datetime.now(TZ)
    if now.tzinfo is None:
        raise ValueError('now должен содержать часовой пояс')
    today=now.astimezone(TZ).date()
    try:
        start,end = date.fromisoformat(promo.get('starts_on') or ''),date.fromisoformat(promo.get('ends_on') or '')
        if start>end: return 'unknown'
    except (ValueError,TypeError):
        return 'unknown'
    if today<start: return 'future'
    if today>end: return 'ended'
    if promo.get('weekdays') and today.weekday() not in promo['weekdays']: return 'off_day'
    return 'active'


def geography(conditions, locations):
    """Извлекает только поддержанные формулировки, оставляя остальные неизвестными."""
    evidence=[]; exclusions=[]
    for paragraph in conditions.splitlines():
        if re.search(r'по всей России', paragraph, re.I):
            evidence.append(paragraph.strip())
            m = re.search(r'кроме\s+(?:ресторанов\s+в\s+)?(?:городах|городов(?:-исключений)?)\s*:?\s*([^.;]+)',paragraph,re.I)
            if 'кроме' in paragraph.casefold() and not m:
                return {'kind':'unknown','evidence':paragraph,'excluded_cities':[],'participant_cities':[],'complete':False}
            if m: exclusions.extend(s.strip() for s in m.group(1).split(',') if s.strip())
    cities=[];complete=True
    for location in locations:
        m=re.search(r'(?:^|,)\s*(?:г\.|пгт\.?|рп\.?|д\.|п\.|с\.)\s+([^,]+)',location,re.I)
        if not m: complete=False
        else: cities.append(m.group(1).strip())
    if locations:
        return {'kind':'participants','evidence':'Список ресторанов-участников на странице акции','excluded_cities':[], 'participant_cities':sorted(set(cities)), 'complete':complete}
    if evidence:
        return {'kind':'nationwide','evidence':'\n'.join(evidence),'excluded_cities':sorted(set(exclusions)),'participant_cities':[],'complete':True}
    return {'kind':'unknown','evidence':None,'excluded_cities':[],'participant_cities':[],'complete':False}


def city_status(promo, city):
    city=normalize_city(city)
    if not city: return 'unknown'
    geo=promo.get('geography') or {}
    if geo.get('kind')=='nationwide':
        return 'not_applicable' if city in {normalize_city(c) for c in geo.get('excluded_cities',[])} else 'applicable'
    if geo.get('kind')=='participants':
        if city in {normalize_city(c) for c in geo.get('participant_cities',[])}: return 'applicable'
        return 'not_applicable' if geo.get('complete') else 'unknown'
    return 'unknown'


def fingerprint(promo):
    content={k:v for k,v in promo.items() if k not in ('retrieved_at','updated_at','listed','content_hash')}
    return hashlib.sha256(json.dumps(content,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
