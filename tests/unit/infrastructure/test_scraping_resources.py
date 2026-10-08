import asyncio

import pytest

from bsentinel._settings import Settings
from bsentinel.infrastructure.scraping import http_fetcher


@pytest.mark.parametrize("key", ["scraping_concurrency", "scheduler_scrape_tick_minutes"])
def test_resource_settings_reject_zero(key):
    with pytest.raises(ValueError):
        Settings(_env_file=None, **{key: 0})


async def test_http_fetches_use_independent_scrapling_sessions(monkeypatch):
    sessions = []
    ready = asyncio.Event()
    release = asyncio.Event()

    class Backend:
        def __init__(self, **kwargs):
            self.active = False
            self.closed = False
            sessions.append(self)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            self.closed = True

        async def get(self, url):
            assert not self.active, "Scrapling session reused concurrently"
            self.active = True
            if sum(s.active for s in sessions) == 3:
                ready.set()
            await release.wait()
            return url

    monkeypatch.setattr(http_fetcher, "FetcherSession", Backend)
    runtime = http_fetcher.HttpFetcherSession(timeout=30, retries=2)
    await runtime.start()
    tasks = [asyncio.create_task(runtime.fetch(str(i))) for i in range(3)]
    try:
        await asyncio.wait_for(ready.wait(), 0.2)
        release.set()
        assert await asyncio.gather(*tasks) == ["0", "1", "2"]
    finally:
        release.set()
        await asyncio.gather(*tasks, return_exceptions=True)
        await runtime.close()
    assert all(session.closed for session in sessions)


@pytest.mark.parametrize("failure", ["exception", "cancel"])
async def test_http_fetch_failure_closes_request_and_lifecycle_sessions(monkeypatch, failure):
    sessions = []
    entered = asyncio.Event()

    class Backend:
        def __init__(self, **kwargs):
            self.closed = False
            self.exit_type = None
            sessions.append(self)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            self.closed = True
            self.exit_type = exc_type

        async def get(self, url):
            entered.set()
            if failure == "exception":
                raise RuntimeError("fixture HTTP failure")
            await asyncio.Event().wait()

    monkeypatch.setattr(http_fetcher, "FetcherSession", Backend)
    runtime = http_fetcher.HttpFetcherSession(timeout=30, retries=0)
    await runtime.start()
    try:
        task = asyncio.create_task(runtime.fetch("https://fixture.invalid/book"))
        await asyncio.wait_for(entered.wait(), 1)
        if failure == "cancel":
            task.cancel()
        expected = asyncio.CancelledError if failure == "cancel" else RuntimeError
        with pytest.raises(expected):
            await task
        assert sessions[1].closed
        assert sessions[1].exit_type is expected
        assert not sessions[0].closed
        assert runtime.is_started
    finally:
        await runtime.close()
    assert len(sessions) == 2
    assert all(session.closed for session in sessions)
    assert not runtime.is_started


async def test_configured_proxy_is_forwarded_on_every_http_request(monkeypatch):
    proxy = "http://fixture:fixture@proxy.fixture.invalid:8080"
    calls = []

    class Backend:
        def __init__(self, **kwargs):
            assert kwargs["proxy"] == proxy

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url, **kwargs):
            calls.append(kwargs.get("proxy"))
            return "fixture response"

    from types import SimpleNamespace

    from bsentinel.infrastructure.scraping.runtime_factory import build_scraping_runtime

    monkeypatch.setattr(http_fetcher, "FetcherSession", Backend)
    runtime = build_scraping_runtime(SimpleNamespace(scraping_http_timeout=3, scraping_http_retries=1,
                                                    scraping_http_proxy=proxy))
    await runtime.start()
    try:
        assert await asyncio.gather(*(runtime.fetch("https://fixture.invalid/" + str(i)) for i in range(3))) == ["fixture response"] * 3
    finally:
        await runtime.close()
    assert calls == [proxy] * 3


async def test_installed_scrapling_invalid_proxy_fails_closed_without_none_override(monkeypatch):
    from scrapling.engines import static

    proxy = "http://127.0.0.1:9"
    merged_proxies, curl_proxies, sessions = [], [], []
    original_merge = static._ConfigurationLogic._merge_request_args

    def merge(self, **kwargs):
        merged_proxies.append(kwargs.get("proxy"))
        return original_merge(self, **kwargs)

    class OfflineCurl:
        def __init__(self):
            self.closed = False
            sessions.append(self)

        async def close(self):
            self.closed = True

        async def request(self, method, **kwargs):
            curl_proxies.append(kwargs.get("proxy"))
            if kwargs.get("proxy") is None:
                raise AssertionError("Direct request forbidden by fixture")
            raise RuntimeError("Invalid proxy fixture; connection refused")

    monkeypatch.setattr(static, "AsyncCurlSession", OfflineCurl)
    monkeypatch.setattr(static._ConfigurationLogic, "_merge_request_args", merge)
    runtime = http_fetcher.HttpFetcherSession(timeout=3, retries=1, proxy=proxy)
    await runtime.start()
    try:
        with pytest.raises(RuntimeError, match="Invalid proxy fixture"):
            await runtime.fetch("https://fixture.invalid/book")
    finally:
        await runtime.close()
    assert merged_proxies == [proxy]
    assert curl_proxies == [proxy]
    assert all(session.closed for session in sessions)
