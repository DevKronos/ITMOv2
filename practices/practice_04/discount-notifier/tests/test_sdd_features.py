"""Контрактные и сквозные HTTP→domain/storage→Jinja проверки лабораторной 5."""
from bs4 import BeautifulSoup
import pytest
from fastapi.testclient import TestClient
from app import storage
from app.domain import search_promotions
from app.main import app


def catalog(html):
    return [h.get_text() for h in BeautifulSoup(html,'html.parser').select('#catalog article h3')]


@pytest.mark.parametrize('query',['СЁМГА','  семга  ','полные   УСЛОВИЯ'])
def test_search_normalization(promo,query):
    p={**promo,'title':'Сёмга','conditions':'Полные\nусловия'}
    assert search_promotions([p],query)==[p]
    assert p['title']=='Сёмга'


def test_search_length_boundaries(promo):
    assert search_promotions([promo],' '*150)==[promo]
    assert search_promotions([promo],'а'*100)==[]
    with pytest.raises(ValueError,match='до 100'): search_promotions([promo],'а'*101)


def test_search_http_full_path(promo):
    storage.import_promotions([promo,{**promo,'source_id':'other','title':'Бонус','conditions':'Сёмга\nполные условия'}])
    with TestClient(app) as client:
        before=client.get('/api/state').json()
        page=client.get('/')
        assert len(catalog(page.text))==2
        soup=BeautifulSoup(page.text,'html.parser')
        form=soup.select_one('#catalog-query').find_parent('form')
        assert form['method']=='get'
        page=client.get(form['action'],params={'q':'  СЕМГА '})
        assert catalog(page.text)==['Бонус']
        assert BeautifulSoup(page.text,'html.parser').select_one('#catalog-query')['value']=='  СЕМГА '
        assert 'badge">1<' in page.text
        assert catalog(client.get('/',params={'q':'нет совпадений'}).text)==[]
        assert 'По вашему запросу акции не найдены' in client.get('/',params={'q':'нет совпадений'}).text
        assert catalog(client.get('/',params={'q':' '*110}).text)==catalog(client.get('/').text)
        error=client.get('/',params={'q':'а'*101})
        assert error.status_code==200 and 'role="alert"' in error.text
        assert len(catalog(error.text))==2
        html=client.get('/',params={'q':'<script>alert(1)</script>'}).text
        assert '<script>alert(1)</script>' not in html and '&lt;script&gt;' in html
        assert client.get('/api/state').json()==before
        assert len(catalog(client.get('/#catalog').text))==2


def test_empty_catalog_search():
    with TestClient(app) as client:
        html=client.get('/',params={'q':'скидка'}).text
        assert 'Нет данных.' in html
        assert 'По вашему запросу акции не найдены' not in html


def seed_city_notes(promo):
    p={**promo,'content_hash':'test-version'}
    storage.set_city('Санкт-Петербург');storage.subscribe('rostics',True)
    storage.add_notifications([p,{**p,'source_id':'second'}],'Санкт-Петербург')
    storage.set_city('Москва');storage.add_notifications([p],'Москва')
    storage.set_city('Санкт-Петербург')


def test_read_city_http_full_path_and_search(promo):
    seed_city_notes(promo);storage.import_promotions([promo])
    with TestClient(app) as client:
        before=client.get('/api/state').json()
        soup=BeautifulSoup(client.get('/',params={'q':'Скидка'}).text,'html.parser')
        form=soup.select_one('form[action="/notifications/read-city"]')
        assert form and not form.select_one('button').has_attr('disabled')
        data={i['name']:i['value'] for i in form.select('input[name]')}
        result=client.post(form['action'],data=data,follow_redirects=False)
        assert result.status_code==303
        page=client.get(result.headers['location'])
        assert 'Отмечено прочитанными: 2' in page.text
        after=client.get('/api/state').json()
        assert sum(n['is_read'] for n in after['notifications'])==2
        assert [n['is_read'] for n in after['notifications'] if n['city']=='Москва']==[0]
        assert len(after['notifications'])==len(before['notifications'])==3
        assert after['city']==before['city'] and after['networks']==before['networks']
        assert after['promotions']==before['promotions']
        assert BeautifulSoup(page.text,'html.parser').select_one('#notifications .badge').text=='0'
        assert BeautifulSoup(page.text,'html.parser').select_one('form[action="/notifications/read-city"] button').has_attr('disabled')
        assert 'Отмечено прочитанными: 0' in client.post(form['action'],data=data).text
        assert catalog(client.get('/',params={'q':'СКИДКА'}).text)==[promo['title']]
    # Новое соединение и новый lifecycle читают сохранённые отметки.
    with TestClient(app) as client:
        assert sum(n['is_read'] for n in client.get('/api/state').json()['notifications'])==2
        moscow=next(n for n in client.get('/api/state').json()['notifications'] if n['city']=='Москва')
        assert client.post(f"/notifications/{moscow['id']}/read").status_code==200
        assert sum(n['is_read'] for n in storage.read_state()['notifications'])==3


def test_read_city_errors_do_not_write(promo):
    seed_city_notes(promo)
    with TestClient(app) as client:
        storage.set_city('Москва');before=storage.read_state()
        stale=client.post('/notifications/read-city',data={'expected_city':'Санкт-Петербург'})
        assert 'Город изменился.' in stale.text
        for value in ('   ','а'*101):
            assert 'Сохраните город перед отметкой уведомлений' in client.post('/notifications/read-city',data={'expected_city':value}).text
        assert client.post('/notifications/read-city').status_code==422
        assert client.post('/notifications/read-city',data={'expected_city':''}).status_code==422
        assert client.post('/notifications/read-city',data={'expected_city':'Москва'},headers={'origin':'https://other.example'}).status_code==403
        assert client.get('/notifications/read-city').status_code==405
        assert storage.read_state()==before


def test_read_city_boundaries_and_aliases(promo):
    with TestClient(app) as client:
        assert BeautifulSoup(client.get('/').text,'html.parser').select_one('form[action="/notifications/read-city"] button').has_attr('disabled')
        assert 'Сохраните город' in client.post('/notifications/read-city',data={'expected_city':'Москва'}).text
        with pytest.raises(ValueError): storage.mark_city_read('')
        storage.set_city('Москва');assert storage.mark_city_read('Москва')==0
        storage.set_city('а'*100);assert storage.mark_city_read('а'*100)==0
        seed_city_notes(promo)
        notes=storage.read_state()['notifications']
        first=next(n for n in notes if n['city']=='Санкт-Петербург')
        storage.mark_read(first['id'])
        assert storage.mark_city_read('  СПб  ')==1
        assert storage.mark_city_read('Санкт-Петербург')==0
        assert sum(n['is_read'] for n in storage.read_state()['notifications'])==2
