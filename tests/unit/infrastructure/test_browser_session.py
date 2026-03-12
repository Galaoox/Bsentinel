import pytest

from bsentinel.infrastructure.scraping import browser as browser_module
from bsentinel.infrastructure.scraping.browser import StealthBrowserSession


class DummyAsyncStealthySession:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.closed = True

    async def fetch(self, url: str):
        return {"url": url}


@pytest.mark.asyncio
async def test_stealth_browser_session_starts_and_fetches(monkeypatch: pytest.MonkeyPatch):
    created: dict[str, object] = {}

    def fake_session(**kwargs):
        instance = DummyAsyncStealthySession(**kwargs)
        created["instance"] = instance
        return instance

    monkeypatch.setattr(browser_module, "AsyncStealthySession", fake_session)

    session = StealthBrowserSession(
        headless=True,
        timeout_ms=45000,
        max_pages=3,
        disable_resources=True,
        network_idle=True,
        solve_cloudflare=False,
        real_chrome=False,
    )

    await session.start()
    result = await session.fetch("https://example.com")

    assert session.is_started is True
    assert result == {"url": "https://example.com"}
    assert created["instance"].kwargs["timeout"] == 45000
    assert created["instance"].kwargs["block_webrtc"] is True
    assert created["instance"].kwargs["hide_canvas"] is True


@pytest.mark.asyncio
async def test_stealth_browser_session_close_resets_state(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(browser_module, "AsyncStealthySession", DummyAsyncStealthySession)
    session = StealthBrowserSession(
        headless=True,
        timeout_ms=45000,
        max_pages=3,
        disable_resources=True,
        network_idle=True,
        solve_cloudflare=False,
        real_chrome=False,
    )

    await session.start()
    await session.close()

    assert session.is_started is False
