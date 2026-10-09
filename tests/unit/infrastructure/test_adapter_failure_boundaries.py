"""Expected transport failures are recoverable; unrelated failures retain identity."""

import asyncio

import pytest
from curl_cffi.curl import CurlError
from curl_cffi.requests import AsyncSession, Response
from curl_cffi.requests.exceptions import Timeout
from patchright.async_api import Error as BrowserError
from patchright.async_api import TimeoutError as BrowserTimeout
from sqlalchemy.exc import OperationalError

from bsentinel.domain.models import Store
from bsentinel.exceptions import ScrapingError
from bsentinel.infrastructure.scraping.browser import StealthBrowserSession
from bsentinel.infrastructure.scraping.configured import ConfiguredStoreScraper
from bsentinel.infrastructure.scraping.http_fetcher import HttpFetcherSession
from bsentinel.infrastructure.scraping.limited_runtime import LimitedRuntime
from bsentinel.infrastructure.scraping.store_guard import MemoryBlockPersistence, StoreGuard

URL = "https://fixture.invalid/book"
PRIVATE = "http://private-user:private-password@proxy.invalid:8080"


def unexpected(kind):
    if kind == "sql":
        return OperationalError("fixture statement", {}, RuntimeError(PRIVATE))
    if kind == "cancel":
        return asyncio.CancelledError(PRIVATE)
    return RuntimeError(PRIVATE)


@pytest.mark.parametrize("stage", ["precheck", "transport_read", "publish", "fetch"])
@pytest.mark.parametrize("kind", ["sql", "unexpected", "cancel"])
async def test_real_http_and_store_guard_preserve_unrelated_error_identity(monkeypatch, caplog, stage, kind):
    error = unexpected(kind)
    requests, events = [], []

    class Persistence(MemoryBlockPersistence):
        reads = 0

        async def read(self, store_id):
            self.reads += 1
            if (stage == "precheck" and self.reads == 1) or (stage == "transport_read" and self.reads == 3):
                raise error
            return await super().read(store_id)

        async def extend(self, store_id, state):
            if stage == "publish":
                raise error
            return await super().extend(store_id, state)

    async def request(self, method, **kwargs):
        requests.append(kwargs["url"])
        if stage == "fetch":
            raise error
        response = Response()
        response.url, response.content = URL, b"<html>fixture</html>"
        response.status_code, response.reason = 405, "fixture"
        response.headers = {"content-type": "text/html", "x-amzn-waf-action": "captcha"}
        return response

    async def sink(event):
        events.append(event)

    monkeypatch.setattr(AsyncSession, "request", request)
    backend = HttpFetcherSession(timeout=1, retries=1, traffic_sink=sink)
    runtime = LimitedRuntime(backend)
    guard = StoreGuard(Persistence())
    scraper = ConfiguredStoreScraper(runtime, store_guard=guard)
    await runtime.start()
    try:
        with pytest.raises(type(error)) as caught:
            await scraper.scrape_book(Store(domain="fixture.invalid"), URL)
        assert caught.value is error
    finally:
        await runtime.close()
    assert requests == ([] if stage in {"precheck", "transport_read"} else [URL])
    assert len(events) == len(requests)
    assert guard.entries == {} and runtime.active == 0
    assert not runtime.is_started
    assert "private-user" not in caplog.text and "private-password" not in caplog.text


@pytest.mark.parametrize("kind", ["curl", "curl_timeout", "timeout"])
async def test_real_http_expected_transport_failure_is_recoverable_and_safe(monkeypatch, caplog, kind):
    response = Response()
    factories = {
        "curl": lambda: CurlError(PRIVATE, 7),
        "curl_timeout": lambda: Timeout(PRIVATE, 28, response),
        "timeout": lambda: TimeoutError(PRIVATE),
    }
    error = factories[kind]()
    events = []

    async def request(self, method, **kwargs):
        raise error

    async def sink(event):
        events.append(event)

    monkeypatch.setattr(AsyncSession, "request", request)
    runtime = HttpFetcherSession(timeout=1, retries=1, traffic_sink=sink)
    scraper = ConfiguredStoreScraper(runtime)
    await runtime.start()
    try:
        with pytest.raises(ScrapingError) as caught:
            await scraper.scrape_book(Store(domain="fixture.invalid"), URL)
    finally:
        await runtime.close()
    assert caught.value.reason == "fetch_failed"
    assert caught.value.__cause__ is error
    assert caught.value.diagnostics["error_type"] == type(error).__name__
    assert "private-user" not in str(caught.value) and "private-password" not in str(caught.value)
    assert "private-user" not in caplog.text and "private-password" not in caplog.text
    if isinstance(error, CurlError):
        assert "private-user" not in str(error) and "private-password" not in str(error)
        assert error.code == (28 if kind == "curl_timeout" else 7)
    if kind == "curl_timeout":
        assert error.response is response
    assert len(events) == 1 and events[0].outcome == "failed"


@pytest.mark.parametrize("kind", ["browser", "browser_timeout", "timeout", "sql", "unexpected", "cancel"])
async def test_browser_boundary_converts_only_expected_errors(monkeypatch, caplog, kind):
    from bsentinel.infrastructure.scraping import browser

    factories = {"browser": lambda: BrowserError(PRIVATE),
                 "browser_timeout": lambda: BrowserTimeout(PRIVATE),
                 "timeout": lambda: TimeoutError(PRIVATE)}
    error = factories[kind]() if kind in factories else unexpected(kind)
    closed = []

    class Session:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            closed.append(True)

        async def fetch(self, url):
            raise error

    monkeypatch.setattr(browser, "AsyncStealthySession", Session)
    runtime = StealthBrowserSession(headless=True, timeout_ms=100, max_pages=3,
                                    disable_resources=True, network_idle=False,
                                    solve_cloudflare=False, real_chrome=False)
    scraper = ConfiguredStoreScraper(runtime)
    await runtime.start()
    try:
        if kind in factories:
            with pytest.raises(ScrapingError) as caught:
                await scraper.scrape_book(Store(domain="fixture.invalid"), URL)
            assert caught.value.reason == "fetch_failed" and caught.value.__cause__ is error
            assert "private-user" not in str(caught.value) and "private-password" not in str(caught.value)
        else:
            with pytest.raises(type(error)) as caught:
                await scraper.scrape_book(Store(domain="fixture.invalid"), URL)
            assert caught.value is error
    finally:
        await runtime.close()
    assert closed == [True] and not runtime.is_started
    assert "private-user" not in caplog.text and "private-password" not in caplog.text
