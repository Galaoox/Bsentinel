import asyncio
import json
from collections import Counter
from datetime import timedelta

import pytest
from curl_cffi import CurlInfo
from curl_cffi.requests import AsyncSession, Response
from curl_cffi.requests.exceptions import Timeout

from bsentinel.application.services.catalog import CatalogCommandService
from bsentinel.application.services.pricing import ScrapingService
from bsentinel.application.services.traffic_context import attribution, traffic_context
from bsentinel.domain.models import Store
from bsentinel.exceptions import ScrapingError
from bsentinel.infrastructure.persistence.in_memory import (
    InMemoryBookRepository,
    InMemoryHistoryRepository,
    InMemoryRelationRepository,
    InMemoryStore,
    InMemoryStoreRepository,
)
from bsentinel.infrastructure.scraping.configured import ConfiguredStoreScraper
from bsentinel.infrastructure.scraping.http_fetcher import HttpFetcherSession
from bsentinel.infrastructure.scraping.rules import build_default_buscalibre_rules


def html(index):
    product = {'@type': 'Product', 'name': f'Title {index}',
               'isbn': f'978032114653{index}', 'author': [{'name': f'Author {index}'}],
               'offers': {'price': 45000 + index, 'lowPrice': 45000 + index,
                          'availability': 'http://schema.org/InStock'}}
    return ('<html><script type="application/ld+json">' + json.dumps(product) + '</script></html>').encode()


class Metadata:
    def __init__(self):
        self.isbns = []

    async def enrich_by_isbn(self, isbn):
        self.isbns.append(isbn)
        # Deliberately interleave metadata with the other operations' fetches.
        await asyncio.sleep(0)
        return {'publisher': 'OpenLibrary fixture'}


def services(scraper):
    memory = InMemoryStore()
    books = InMemoryBookRepository(memory)
    stores = InMemoryStoreRepository(memory)
    relations = InMemoryRelationRepository(memory)
    history = InMemoryHistoryRepository(memory)
    metadata = Metadata()
    command = CatalogCommandService(books=books, stores=stores, relations=relations,
                                    metadata=metadata, scraper=scraper)
    pricing = ScrapingService(books=books, stores=stores, relations=relations,
                             history=history, scraper=scraper)
    return memory, metadata, command, pricing


@pytest.mark.parametrize('retry', [False, True])
async def test_three_concurrent_creations_keep_values_and_traffic_isolated(monkeypatch, retry):
    events, requests = [], []
    counts = Counter()

    async def sink(event):
        events.append(event)

    async def request(self, method, **kwargs):
        url = kwargs['url']
        index = int(url.rsplit('/', 1)[1])
        counts[url] += 1
        requests.append((url, kwargs.get('proxy')))
        await asyncio.sleep(0)
        result = Response()
        result.url, result.content, result.status_code, result.reason = url, html(index), 200, 'OK'
        result.headers = {'content-type': 'text/html'}
        result.infos = {CurlInfo.SIZE_DOWNLOAD_T: 100 + index, CurlInfo.SIZE_UPLOAD_T: 0,
                        CurlInfo.REQUEST_SIZE: 90, CurlInfo.HEADER_SIZE: 40, CurlInfo.REDIRECT_COUNT: 0}
        if retry and counts[url] == 1:
            raise Timeout('offline fixture', 28, result)
        return result

    monkeypatch.setattr(AsyncSession, 'request', request)
    runtime = HttpFetcherSession(timeout=1, retries=2, proxy='http://fixture.invalid:8080', traffic_sink=sink)
    await runtime.start()
    scraper = ConfiguredStoreScraper(browser_session=runtime)
    memory, metadata, command, pricing = services(scraper)
    urls = ['https://www.buscalibre.com.co/1', 'https://www.panamericana.com.co/2',
            'https://www.buscalibre.com.co/3']

    async def create(index, url):
        with traffic_context(scope='catalog', operation_id=f'operation-{index}'):
            book, relation, domain, result = await command.create_book_from_url(url)
            await asyncio.sleep(0)
            await pricing.record_result(relation, result)
            return book, relation, result

    try:
        created = await asyncio.gather(*(create(i, url) for i, url in enumerate(urls, start=1)))
    finally:
        await runtime.close()
    for index, (book, relation, result) in enumerate(created, start=1):
        assert book.title == f'Title {index}'
        assert book.authors == [f'Author {index}']
        assert book.isbn == f'978032114653{index}'
        assert book.publisher == 'OpenLibrary fixture'
        assert relation.current_price == 45000 + index
        assert relation.last_checked == result.checked_at
        assert relation.scrape_generation == 0
        assert relation.next_check_at >= result.checked_at + timedelta(hours=1)
        records = [r for r in memory.history.values() if r.relation_id == relation.id]
        assert len(records) == 1
        assert records[0].checked_at == result.checked_at
        attempts = [e for e in events if e.operation_id == f'operation-{index}']
        assert [e.outcome for e in attempts] == (['failed', 'successful'] if retry else ['successful'])
        assert all(e.scope == 'catalog' and e.download_bytes == 100 + index for e in attempts)
        assert all(e.domain == relation.product_url.split('/')[2] for e in attempts)
    assert counts == {url: 2 if retry else 1 for url in urls}
    assert all(proxy == 'http://fixture.invalid:8080' for _, proxy in requests)
    assert Counter(metadata.isbns) == {f'978032114653{i}': 1 for i in range(1, 4)}
    assert attribution.get() == {}


@pytest.mark.parametrize('kind,expected_calls,reason', [
    ('http_error', 1, 'http_error'),
    ('interstitial', 3, 'interstitial_transient_exhausted'),
    ('missing_author', 1, 'authors_not_found'),
])
async def test_combined_extraction_preserves_response_validation_and_retry_bounds(kind, expected_calls, reason):
    from scrapling.engines.toolbelt.custom import Response as Page

    calls = []

    class Session:
        async def fetch(self, url):
            calls.append(url)
            body = html(1)
            status = 200
            if kind == 'http_error':
                status = 403
            elif kind == 'interstitial':
                body, status = b'<html>Just a moment captcha</html>', 202
            else:
                body = body.replace(b'"author": [{"name": "Author 1"}]', b'"author": []')
            return Page(url=url, content=body, status=status, reason='fixture', cookies={},
                        headers={'content-type': 'text/html'}, request_headers={}, encoding='utf-8')

    scraper = ConfiguredStoreScraper(browser_session=Session(), transient_retry_delay_ms=0)
    memory, metadata, command, _ = services(scraper)
    with pytest.raises(ScrapingError) as error:
        await command.create_book_from_url('https://www.buscalibre.com.co/1')
    assert error.value.reason == reason
    assert len(calls) == expected_calls
    assert not metadata.isbns
    assert not memory.books and not memory.relations and not memory.history


async def test_future_configured_store_uses_combined_extraction_without_cache():
    from scrapling.engines.toolbelt.custom import Response as Page

    calls = []

    class Session:
        async def fetch(self, url):
            calls.append(url)
            return Page(url=url, content=html(len(calls)), status=200, reason='OK', cookies={},
                        headers={'content-type': 'text/html'}, request_headers={}, encoding='utf-8')

    scraper = ConfiguredStoreScraper(browser_session=Session())
    store = Store(domain='future-store.invalid', extraction_rules=build_default_buscalibre_rules())
    url = 'https://future-store.invalid/product'
    first = await scraper.extract_product(store, url)
    second = await scraper.extract_product(store, url)
    assert calls == [url, url]
    assert first.details.title == 'Title 1'
    assert first.result.price == 45001
    assert second.details.title == 'Title 2'
    assert second.result.price == 45002
    assert not hasattr(first, 'page')
    assert not hasattr(first, 'html')
