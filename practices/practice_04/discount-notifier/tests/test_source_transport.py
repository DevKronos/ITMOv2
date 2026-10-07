"""Проверки транспорта без сети и реального ожидания."""
import errno
import socket
import ssl
from collections import Counter
from http.client import IncompleteRead
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest
from app import storage
from app.service import synchronize
from app.source import CATALOG, SourceError, collect_live, fetch_html

SNAP=Path(__file__).resolve().parents[1]/'research/snapshots'


class Response:
    status=200
    headers={}
    url=CATALOG

    def __init__(self,body=b'<h1>test</h1>',error=None):
        self.body=body;self.error=error;self.closed=False

    def __enter__(self): return self

    def __exit__(self,*args): self.closed=True

    def read(self,size):
        assert size==5_000_001
        if self.error: raise self.error
        return self.body


@pytest.mark.parametrize('error',[
    URLError(TimeoutError('timed out')),
    ConnectionResetError('connection reset'),
    URLError(socket.gaierror(socket.EAI_AGAIN,'temporary DNS failure')),
    HTTPError(CATALOG,503,'Unavailable',{},None),
])
def test_transient_failure_then_success(error):
    calls=[];pauses=[];response=Response()
    def transport(request,timeout):
        calls.append((request.full_url,timeout))
        if len(calls)==1: raise error
        return response
    assert fetch_html(CATALOG,transport=transport,wait=pauses.append)=='<h1>test</h1>'
    assert calls==[(CATALOG,20)]*2
    assert pauses==[.5] and response.closed


def test_exhausted_attempts_include_url_and_reason():
    calls=[];pauses=[]
    def transport(request,timeout):
        calls.append(request.full_url)
        raise URLError(TimeoutError('timed out'))
    with pytest.raises(SourceError) as caught:
        fetch_html(CATALOG,transport=transport,wait=pauses.append)
    assert calls==[CATALOG]*3 and pauses==[.5,1.0]
    assert CATALOG in str(caught.value) and 'TimeoutError: timed out' in str(caught.value)
    assert 'попыток: 3' in str(caught.value)


@pytest.mark.parametrize('error',[
    HTTPError(CATALOG,403,'Forbidden',{},None),
    HTTPError(CATALOG,404,'Not found',{},None),
    HTTPError(CATALOG,429,'Too many requests',{'Retry-After':'120'},None),
    URLError(ssl.SSLCertVerificationError('certificate verify failed')),
    URLError(socket.gaierror(socket.EAI_NONAME,'unknown host')),
    URLError(OSError(errno.ENETUNREACH,'Network is unreachable')),
    URLError('unclassified failure'),
])
def test_permanent_or_unclassified_error_is_not_retried(error):
    calls=[];pauses=[]
    def transport(request,timeout):
        calls.append(request.full_url);raise error
    with pytest.raises(SourceError,match='попыток: 1'):
        fetch_html(CATALOG,transport=transport,wait=pauses.append)
    assert calls==[CATALOG] and pauses==[]


def test_read_failure_is_retried_and_responses_closed():
    responses=[Response(error=IncompleteRead(b'partial',20)),Response()]
    calls=[];pauses=[]
    def transport(request,timeout):
        response=responses[len(calls)];calls.append(request.full_url);return response
    assert fetch_html(CATALOG,transport=transport,wait=pauses.append)=='<h1>test</h1>'
    assert len(calls)==2 and pauses==[.5] and all(r.closed for r in responses)


@pytest.mark.parametrize('change', ['redirect','oversize','decode'])
def test_response_validation_is_not_retried(change):
    response=Response();calls=[];pauses=[]
    if change=='redirect': response.url='https://example.org/promo'
    elif change=='oversize': response.body=b'x'*5_000_001
    else: response.body=b'\xff'
    def transport(request,timeout): calls.append(request.full_url);return response
    with pytest.raises(SourceError,match='попыток: 1'):
        fetch_html(CATALOG,transport=transport,wait=pauses.append)
    assert len(calls)==1 and pauses==[] and response.closed


def test_partial_import_and_parser_failure_do_not_redownload(promo):
    storage.import_promotions([promo])
    calls=Counter();pauses=[]
    urls=[CATALOG+'/dishfrom1799',CATALOG+'/thosewhorule',CATALOG+'/bsk15']
    catalog='<h1>Акции</h1>'+''.join(f'<a href="{url.removeprefix("https://rostics.ru")}">promo</a>' for url in urls)
    def transport(request,timeout):
        url=request.full_url;calls[url]+=1
        if url==CATALOG: return Response(catalog.encode())
        if url.endswith('/dishfrom1799'):
            return Response((SNAP/'https_rostics_ru_promo_dishfrom1799.html').read_bytes())
        if url.endswith('/thosewhorule'): raise URLError(TimeoutError('timed out'))
        return Response(b'<h1>Broken markup</h1>')
    def fetch(url): return fetch_html(url,transport=transport,wait=pauses.append)
    result=synchronize(collector=lambda:collect_live(fetch))
    assert result['status']=='partial' and result['links_found']==3 and result['fetched']==1
    assert result['inserted']==1 and len(result['errors'])==2
    assert calls==Counter({CATALOG:1,urls[0]:1,urls[1]:3,urls[2]:1})
    assert pauses==[.5,1.0]
    state=storage.read_state()
    assert {p['source_id'] for p in state['promotions']}=={'test','dishfrom1799'}
    assert all(p['listed'] for p in state['promotions'])
    assert 'попыток: 3' in next(e['error'] for e in result['errors'] if e['url']==urls[1])
