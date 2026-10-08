import pytest
from scrapling.engines.toolbelt.custom import Response

from bsentinel.domain.models import Store
from bsentinel.exceptions import ScrapingError
from bsentinel.infrastructure.scraping.configured import ConfiguredStoreScraper
from bsentinel.infrastructure.scraping.rules import build_default_buscalibre_rules

PRODUCT = '''<html><script type="application/ld+json">{"@type":"Product","name":"Understanding captcha","author":{"name":"Fixture"},"isbn":"9780321146533","offers":{"price":"123"}}</script><p>captcha</p></html>'''
AWS = '<html><title>Human Verification</title><script src="https://fixture.token.awswaf.com/fixture/challenge.js"></script><div id="awswaf-captcha-container"></div></html>'


def response(body=AWS, status=405, headers=None):
    return Response(url='https://fixture.invalid/book', content=body, status=status,
                    reason='fixture', cookies={}, headers=headers or {'content-type': 'text/html'},
                    request_headers={}, encoding='utf-8')


class Transport:
    def __init__(self, page):
        self.page = page
        self.calls = 0

    async def fetch(self, url):
        self.calls += 1
        return self.page


@pytest.mark.parametrize('status,headers,body,reason', [
    (405, {'x-amzn-waf-action': 'captcha'}, '', 'captcha_blocked'),
    (405, {'X-AmZn-WaF-AcTiOn': ' CaPtChA '}, '', 'captcha_blocked'),
    (202, {'x-amzn-waf-action': 'challenge'}, '', 'challenge_blocked'),
    (405, {}, AWS, 'captcha_blocked'),
    (200, {}, AWS, 'captcha_blocked'),
    (405, {}, '<h1>Method not allowed</h1>', 'http_error'),
])
async def test_block_signals_precede_http_error_without_retry(status, headers, body, reason):
    transport = Transport(response(body, status, headers))
    scraper = ConfiguredStoreScraper(transport, transient_retry_delay_ms=0)
    with pytest.raises(ScrapingError) as caught:
        await scraper.extract_product(Store(domain='fixture.invalid'), 'https://fixture.invalid/book?private=1')
    assert caught.value.reason == reason
    assert transport.calls == 1
    assert 'private=1' not in str(caught.value.diagnostics)


async def test_product_mentioning_captcha_is_usable():
    transport = Transport(response(PRODUCT, 200))
    scraper = ConfiguredStoreScraper(transport, transient_retry_delay_ms=0)
    product = await scraper.extract_product(Store(extraction_rules=build_default_buscalibre_rules()), 'https://fixture.invalid/book')
    assert product.result.price == 123
    assert transport.calls == 1


async def test_shared_guard_persists_across_scrapers_entrypoints_and_expiry():
    from datetime import UTC, datetime, timedelta

    from bsentinel.infrastructure.scraping.limited_runtime import LimitedRuntime
    from bsentinel.infrastructure.scraping.store_guard import MemoryBlockPersistence, StoreGuard
    now = [datetime(2026, 10, 8, 13, tzinfo=UTC)]
    persistence = MemoryBlockPersistence()
    guard = StoreGuard(persistence, clock=lambda: now[0])
    transport = Transport(response())
    runtime = LimitedRuntime(transport)
    scraper = ConfiguredStoreScraper(runtime, store_guard=guard)
    store = Store(domain='fixture.invalid', extraction_rules=build_default_buscalibre_rules())
    with pytest.raises(ScrapingError) as blocked:
        await scraper.scrape_book(store, 'https://fixture.invalid/book')
    assert blocked.value.reason == 'captcha_blocked'
    restarted = ConfiguredStoreScraper(runtime, store_guard=StoreGuard(persistence, clock=lambda: now[0]))
    for entry in [restarted.scrape_book, restarted.extract_book_details, restarted.extract_product]:
        with pytest.raises(ScrapingError) as paused:
            await entry(store, 'https://fixture.invalid/book')
        assert paused.value.reason == 'store_paused'
    assert transport.calls == 1
    transport.page = response(PRODUCT, 200)
    other = Store(domain='other.invalid', extraction_rules=build_default_buscalibre_rules())
    assert (await scraper.scrape_book(other, 'https://other.invalid/book')).price == 123
    now[0] += timedelta(minutes=60)
    assert (await restarted.extract_product(store, 'https://fixture.invalid/book')).result.price == 123
    assert transport.calls == 3


async def test_queued_requests_recheck_pause_inside_global_permit():
    import asyncio

    from bsentinel.infrastructure.scraping.limited_runtime import LimitedRuntime
    from bsentinel.infrastructure.scraping.store_guard import MemoryBlockPersistence, StoreGuard
    transport = Transport(response())
    runtime = LimitedRuntime(transport, concurrency=1)
    guard = StoreGuard(MemoryBlockPersistence())
    scraper = ConfiguredStoreScraper(runtime, store_guard=guard)
    store = Store(domain='fixture.invalid')
    results = await asyncio.gather(*[scraper.extract_product(store, 'https://fixture.invalid/book') for _ in range(10)], return_exceptions=True)
    assert [e.reason for e in results].count('captcha_blocked') == 1
    assert [e.reason for e in results].count('store_paused') == 9
    assert transport.calls == 1
    assert not guard.entries


async def test_expired_store_allows_one_half_open_probe_and_inflight_success_cannot_clear_new_block():
    import asyncio
    from datetime import UTC, datetime, timedelta

    from bsentinel.infrastructure.scraping.limited_runtime import LimitedRuntime
    from bsentinel.infrastructure.scraping.store_guard import (
        BlockState,
        MemoryBlockPersistence,
        StoreGuard,
    )
    now = datetime(2026, 10, 8, 14, tzinfo=UTC)
    persistence = MemoryBlockPersistence()
    guard = StoreGuard(persistence, clock=lambda: now)
    store = Store(domain='fixture.invalid', extraction_rules=build_default_buscalibre_rules())
    await persistence.extend(store.id, BlockState(now, 'captcha_blocked'))
    entered, release = asyncio.Event(), asyncio.Event()
    class BlockingTransport(Transport):
        async def fetch(self, url):
            self.calls += 1
            entered.set()
            await release.wait()
            return self.page
    transport = BlockingTransport(response(PRODUCT, 200))
    scraper = ConfiguredStoreScraper(LimitedRuntime(transport), store_guard=guard)
    probe = asyncio.create_task(scraper.extract_product(store, 'https://fixture.invalid/book'))
    await entered.wait()
    others = await asyncio.gather(*[scraper.scrape_book(store, 'https://fixture.invalid/book') for _ in range(5)], return_exceptions=True)
    assert all(e.reason == 'store_paused' for e in others)
    assert transport.calls == 1
    newer = BlockState(now + timedelta(minutes=70), 'challenge_blocked')
    await persistence.extend(store.id, newer)
    release.set()
    assert (await probe).result.price == 123
    assert await persistence.read(store.id) == newer
    assert not guard.entries


async def test_transport_retry_stops_when_another_inflight_request_opens_circuit(monkeypatch):
    from datetime import UTC, datetime, timedelta

    from curl_cffi.requests import AsyncSession
    from curl_cffi.requests.exceptions import Timeout

    from bsentinel.infrastructure.scraping.http_fetcher import HttpFetcherSession
    from bsentinel.infrastructure.scraping.limited_runtime import LimitedRuntime
    from bsentinel.infrastructure.scraping.store_guard import (
        BlockState,
        MemoryBlockPersistence,
        StoreGuard,
    )
    persistence = MemoryBlockPersistence()
    guard = StoreGuard(persistence)
    store = Store(domain='fixture.invalid')
    events, calls = [], []
    async def sink(event):
        events.append(event)
    async def request(self, method, **kwargs):
        calls.append(kwargs['url'])
        await persistence.extend(store.id, BlockState(datetime.now(UTC) + timedelta(hours=1), 'captcha_blocked'))
        raise Timeout('offline fixture', 28)
    monkeypatch.setattr(AsyncSession, 'request', request)
    backend = HttpFetcherSession(timeout=1, retries=2, traffic_sink=sink)
    backend._config['retry_delay'] = 0
    runtime = LimitedRuntime(backend)
    await runtime.start()
    try:
        with pytest.raises(ScrapingError) as caught:
            await ConfiguredStoreScraper(runtime, store_guard=guard).scrape_book(store, 'https://fixture.invalid/book')
        assert caught.value.reason == 'store_paused'
    finally:
        await runtime.close()
    assert len(calls) == len(events) == 1
    assert events[0].outcome == 'failed'


async def test_three_inflight_block_responses_cannot_admit_remaining_queue():
    import asyncio

    from bsentinel.infrastructure.scraping.limited_runtime import LimitedRuntime
    from bsentinel.infrastructure.scraping.store_guard import MemoryBlockPersistence, StoreGuard
    entered, release = asyncio.Event(), asyncio.Event()
    class ThreeTransport(Transport):
        async def fetch(self, url):
            self.calls += 1
            if self.calls == 3:
                entered.set()
            await release.wait()
            return self.page
    backend = ThreeTransport(response())
    runtime = LimitedRuntime(backend)
    scraper = ConfiguredStoreScraper(runtime, store_guard=StoreGuard(MemoryBlockPersistence()))
    store = Store(domain='fixture.invalid')
    tasks = [asyncio.create_task(scraper.extract_product(store, 'https://fixture.invalid/book')) for _ in range(15)]
    await asyncio.wait_for(entered.wait(), 1)
    release.set()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    assert [result.reason for result in results].count('captcha_blocked') == 3
    assert [result.reason for result in results].count('store_paused') == 12
    assert backend.calls == runtime.peak_active == 3


async def test_known_paused_store_fails_fast_even_if_other_stores_occupy_budget():
    import asyncio
    from datetime import UTC, datetime, timedelta

    from bsentinel.infrastructure.scraping.limited_runtime import LimitedRuntime
    from bsentinel.infrastructure.scraping.store_guard import (
        BlockState,
        MemoryBlockPersistence,
        StoreGuard,
    )
    persistence = MemoryBlockPersistence()
    store = Store(domain='fixture.invalid')
    await persistence.extend(store.id, BlockState(datetime.now(UTC) + timedelta(hours=1), 'captcha_blocked'))
    backend = Transport(response())
    runtime = LimitedRuntime(backend, concurrency=1)
    await runtime._permits.acquire()
    try:
        with pytest.raises(ScrapingError) as caught:
            await asyncio.wait_for(ConfiguredStoreScraper(runtime, store_guard=StoreGuard(persistence)).scrape_book(store, 'https://fixture.invalid/book'), .1)
        assert caught.value.reason == 'store_paused'
    finally:
        runtime._permits.release()
    assert backend.calls == 0
