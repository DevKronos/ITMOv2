import pytest


@pytest.fixture(autouse=True)
def isolated_db(tmp_path,monkeypatch):
    monkeypatch.setenv('APP_DB_PATH',str(tmp_path/'test.sqlite'))
    monkeypatch.setenv('APP_BACKGROUND','0')
    monkeypatch.delenv('APP_SNAPSHOT_DIR',raising=False)


@pytest.fixture
def promo():
    return {'network':'rostics','source_id':'test','source_url':'https://rostics.ru/promo/test','title':'Скидка 20%',
            'conditions':'Демонстрационная запись только для теста', 'discount_text':'20%', 'period_text':'с 1 октября по 31 октября 2026 года',
            'starts_on':'2026-10-01','ends_on':'2026-10-31','weekdays':[], 'participating_locations':[],
            'geography':{'kind':'nationwide','excluded_cities':['Якутск'],'participant_cities':[],'complete':True,'evidence':'По всей России, кроме Якутска'},
            'retrieved_at':'2026-10-07T00:00:00+00:00'}
