"""Creation exercises the real configured adapter over offline HTTP responses."""
import importlib
import json
from collections import Counter

import pytest
from scrapling.engines.toolbelt.custom import Response

from bsentinel.infrastructure.scraping.configured import ConfiguredStoreScraper


class ProductSession:
    def __init__(self, price=45900):
        self.calls = []
        self.price = price

    async def fetch(self, url):
        self.calls.append(url)
        product = {
            '@type': 'Product', '@id': url, 'name': 'Single response',
            'isbn': '9780321146533', 'author': [{'name': 'Kent Beck'}],
            'offers': {'price': self.price, 'lowPrice': self.price,
                       'availability': 'https://schema.org/InStock'},
        }
        return Response(url=url, content='<html><script type="application/ld+json">'
                        + json.dumps(product) + '</script></html>', status=200,
                        reason='OK', cookies={}, headers={'content-type': 'text/html'},
                        request_headers={}, encoding='utf-8')


def auth(client):
    response = client.post('/api/v1/auth/login', data={'username': 'admin', 'password': 'changeme'})
    assert response.status_code == 200
    return {'Authorization': 'Bearer ' + response.json()['access_token']}


@pytest.mark.parametrize('domain', ['buscalibre.com.co', 'panamericana.com.co'])
@pytest.mark.parametrize('bulk', [False, True])
def test_creation_fetches_one_response_for_details_and_initial_price(client, monkeypatch, domain, bulk):
    module = importlib.import_module('bsentinel.infrastructure.api.root_app')
    session = ProductSession()
    monkeypatch.setattr(module, 'scraper_client', ConfiguredStoreScraper(browser_session=session))
    url = f'https://{domain}/book/p?ref=affiliate%2Fid#details'
    canonical = url.replace(domain, 'www.' + domain)
    headers = auth(client)
    response = client.post('/api/v1/catalog/books' + ('/bulk' if bulk else ''),
                           json={'urls': [url]} if bulk else {'url': url}, headers=headers)
    assert response.status_code == 201, response.text
    item = response.json()['items'][0] if bulk else response.json()
    assert item['isbn'] == '9780321146533'
    assert item['site'] == 'www.' + domain
    if bulk:
        assert item['url'] == url
    detail = client.get('/api/v1/catalog/books/' + item['book_id'], headers=headers).json()
    assert detail['stores'][0]['price'] == 45900
    assert detail['stores'][0]['last_checked'] is not None
    history = client.get('/api/v1/pricing/books/' + item['book_id'] + '/history', headers=headers).json()
    assert history['meta']['total'] == 1
    # SQLite history loses its timezone suffix; compare the persisted instant.
    assert history['records'][0]['checked_at'].removesuffix('+00:00') == detail['stores'][0]['last_checked'].removesuffix('+00:00')
    assert Counter(session.calls) == {canonical: 1}


@pytest.mark.parametrize('price', [float('nan'), float('inf'), -10])
@pytest.mark.parametrize('bulk', [False, True])
def test_invalid_numeric_price_rejected_before_commit(client, monkeypatch, price, bulk):
    module = importlib.import_module('bsentinel.infrastructure.api.root_app')
    session = ProductSession(price)
    monkeypatch.setattr(module, 'scraper_client', ConfiguredStoreScraper(browser_session=session))
    monkeypatch.setattr(client._transport, 'raise_server_exceptions', False)
    headers = auth(client)
    url = 'https://www.buscalibre.com.co/book/p'
    response = client.post('/api/v1/catalog/books' + ('/bulk' if bulk else ''),
                           json={'urls': [url]} if bulk else {'url': url}, headers=headers)
    assert response.status_code == 400, response.text
    assert response.json()['error']['code'] == 'SCRAPING_ERROR'
    import sqlite3
    path = module.settings.database_url.removeprefix('sqlite+aiosqlite:///')
    assert 'bsentinel-test-' in path
    with sqlite3.connect(f'file:{path}?mode=ro', uri=True) as connection:
        counts = tuple(connection.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
                       for table in ['books', 'book_store_relations', 'price_history'])
    assert counts == (0, 0, 0)
    assert session.calls == [url]


@pytest.mark.parametrize('failure', [None, 'price', 'author', 'empty', 'http'])
def test_real_adapter_bulk_mixed_stores_is_atomic(client, monkeypatch, failure):
    module = importlib.import_module('bsentinel.infrastructure.api.root_app')

    class Session(ProductSession):
        async def fetch(self, url):
            if 'panamericana' in url and failure == 'price':
                self.price = -1
            page = await super().fetch(url)
            if 'panamericana' in url and failure in {'author', 'empty', 'http'}:
                body = bytes(page.body).decode()
                if failure == 'author':
                    body = body.replace('"author": [{"name": "Kent Beck"}]', '"author": []')
                elif failure == 'empty':
                    body = ''
                page = Response(url=url, content=body, status=403 if failure == 'http' else 200,
                                reason='fixture', cookies={}, headers={'content-type': 'text/html'},
                                request_headers={}, encoding='utf-8')
            return page

    session = Session()
    monkeypatch.setattr(module, 'scraper_client', ConfiguredStoreScraper(browser_session=session))
    headers = auth(client)
    urls = ['https://buscalibre.com.co/book/p', 'https://panamericana.com.co/book/p']
    response = client.post('/api/v1/catalog/books/bulk', json={'urls': urls}, headers=headers)
    assert response.status_code == (400 if failure else 201), response.text
    assert Counter(session.calls) == {url.replace('://', '://www.'): 1 for url in urls}
    import sqlite3
    path = module.settings.database_url.removeprefix('sqlite+aiosqlite:///')
    assert 'bsentinel-test-' in path
    with sqlite3.connect(f'file:{path}?mode=ro', uri=True) as connection:
        counts = tuple(connection.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
                       for table in ['books', 'book_store_relations', 'price_history'])
        generations = connection.execute('SELECT scrape_generation FROM book_store_relations').fetchall()
    assert counts == ((0, 0, 0) if failure else (1, 2, 2))
    if failure:
        details = response.json()['error']['details']
        assert details['index'] == 1 and details['url'] == urls[1]
        assert details['scraping_reason']
    else:
        assert generations == [(0,), (0,)]
        assert [item['url'] for item in response.json()['items']] == urls


@pytest.mark.parametrize('bulk', [False, True])
@pytest.mark.parametrize('failure', [None, 'retry_exhausted', 'corrupt_price'])
def test_catalog_transport_attempts_are_attributed_even_on_failed_creation(client, monkeypatch, bulk, failure):
    from curl_cffi import CurlInfo
    from curl_cffi.requests import AsyncSession
    from curl_cffi.requests import Response as CurlResponse
    from curl_cffi.requests.exceptions import Timeout

    from bsentinel.infrastructure.scraping.http_fetcher import HttpFetcherSession

    module = importlib.import_module('bsentinel.infrastructure.api.root_app')
    events, proxies = [], []

    async def sink(event):
        events.append(event)

    async def request(self, method, **kwargs):
        proxies.append(kwargs.get('proxy'))
        fixture = await ProductSession(float('nan') if failure == 'corrupt_price' else 45900).fetch(kwargs['url'])
        result = CurlResponse()
        result.url, result.content, result.status_code, result.reason = kwargs['url'], bytes(fixture.body), 200, 'OK'
        result.headers = {'content-type': 'text/html'}
        result.infos = {CurlInfo.SIZE_DOWNLOAD_T: 250, CurlInfo.SIZE_UPLOAD_T: 0,
                        CurlInfo.REQUEST_SIZE: 90, CurlInfo.HEADER_SIZE: 40, CurlInfo.REDIRECT_COUNT: 0}
        if failure == 'retry_exhausted':
            raise Timeout('offline timeout fixture', 28, result)
        return result

    monkeypatch.setattr(AsyncSession, 'request', request)
    runtime = HttpFetcherSession(timeout=1, retries=2, proxy='http://fixture.invalid:8080', traffic_sink=sink)
    client.portal.call(runtime.start)
    monkeypatch.setattr(module, 'scraper_client', ConfiguredStoreScraper(browser_session=runtime))
    url = 'https://www.buscalibre.com.co/book/p'
    try:
        response = client.post('/api/v1/catalog/books' + ('/bulk' if bulk else ''),
                               json={'urls': [url]} if bulk else {'url': url}, headers=auth(client))
    finally:
        client.portal.call(runtime.close)
    assert response.status_code == (400 if failure else 201), response.text
    expected = 2 if failure == 'retry_exhausted' else 1
    assert proxies == ['http://fixture.invalid:8080'] * expected
    assert len(events) == expected
    assert all(e.scope == 'catalog' and e.operation_id == response.headers['X-Request-ID'] for e in events)
    assert all(e.download_bytes == 250 and e.domain == 'www.buscalibre.com.co' for e in events)
    assert [e.outcome for e in events] == (['failed', 'failed'] if failure == 'retry_exhausted' else ['successful'])
    assert client.get('/api/v1/catalog/books', headers=auth(client)).json()['meta']['total'] == (0 if failure else 1)
