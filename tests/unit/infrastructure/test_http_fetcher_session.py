import pytest

from bsentinel.infrastructure.scraping import http_fetcher as http_fetcher_module
from bsentinel.infrastructure.scraping.http_fetcher import HttpFetcherSession


class DummyFetcherClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def get(self, url: str, **kwargs):
        self.calls.append((url, kwargs))
        return {"url": url, "kwargs": kwargs}


class DummyFetcherManager:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.client = DummyFetcherClient()
        self.closed = False

    async def __aenter__(self):
        return self.client

    async def __aexit__(self, exc_type, exc, tb):
        self.closed = True


class FailingFetcherClient:
    async def get(self, url: str, **kwargs):
        raise RuntimeError("proxy tunnel failed via http://user:pass@proxy.example:8080")


class FailingFetcherManager(DummyFetcherManager):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.client = FailingFetcherClient()


@pytest.mark.asyncio
async def test_http_fetcher_session_starts_fetches_and_closes(monkeypatch: pytest.MonkeyPatch):
    created: dict[str, DummyFetcherManager] = {}

    def fake_manager(**kwargs):
        manager = DummyFetcherManager(**kwargs)
        created["manager"] = manager
        return manager

    monkeypatch.setattr(http_fetcher_module, "FetcherSession", fake_manager)

    session = HttpFetcherSession(
        timeout=15,
        retries=4,
        impersonate="chrome",
        http3=True,
        stealthy_headers=False,
        proxy="http://user:pass@proxy.example:8080",
    )

    await session.start()
    result = await session.fetch("https://example.com/book")
    await session.close()

    assert session.is_started is False
    assert result == {"url": "https://example.com/book", "kwargs": {}}
    assert created["manager"].kwargs == {
        "timeout": 15,
        "retries": 4,
        "impersonate": "chrome",
        "http3": True,
        "stealthy_headers": False,
        "proxy": "http://user:pass@proxy.example:8080",
    }
    assert created["manager"].client.calls == [("https://example.com/book", {})]
    assert created["manager"].closed is True


@pytest.mark.asyncio
async def test_http_fetcher_session_start_is_idempotent(monkeypatch: pytest.MonkeyPatch):
    created: list[DummyFetcherManager] = []

    def fake_manager(**kwargs):
        manager = DummyFetcherManager(**kwargs)
        created.append(manager)
        return manager

    monkeypatch.setattr(http_fetcher_module, "FetcherSession", fake_manager)

    session = HttpFetcherSession(timeout=30, retries=2)

    await session.start()
    await session.start()

    assert session.is_started is True
    assert len(created) == 1


@pytest.mark.asyncio
async def test_http_fetcher_session_requires_started_runtime():
    session = HttpFetcherSession(timeout=30, retries=2)

    with pytest.raises(RuntimeError, match="HTTP fetcher session is not initialized"):
        await session.fetch("https://example.com/book")


@pytest.mark.asyncio
async def test_http_fetcher_session_sanitizes_proxy_credentials_on_fetch_error(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(http_fetcher_module, "FetcherSession", lambda **kwargs: FailingFetcherManager(**kwargs))

    session = HttpFetcherSession(timeout=30, retries=2, proxy="http://user:pass@proxy.example:8080")
    await session.start()

    with pytest.raises(RuntimeError) as exc_info:
        await session.fetch("https://example.com/book")

    assert "http://***:***@proxy.example:8080" in str(exc_info.value)
    assert "http://user:pass@proxy.example:8080" not in str(exc_info.value)
