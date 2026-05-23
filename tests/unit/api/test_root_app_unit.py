import importlib
import json
from contextlib import AsyncExitStack
from types import SimpleNamespace

import pytest

from bsentinel.exceptions import ScrapingError
from bsentinel.infrastructure.api.root_app import (
    global_exception_handler,
    health_check,
    root,
    standard_exception_handler,
)

root_app_module = importlib.import_module("bsentinel.infrastructure.api.root_app")


class RuntimeStub:
    def __init__(self) -> None:
        self.start_calls = 0
        self.close_calls = 0
        self._is_started = False

    async def start(self) -> None:
        self.start_calls += 1
        self._is_started = True

    async def close(self) -> None:
        self.close_calls += 1
        self._is_started = False

    async def fetch(self, url: str):
        return {"url": url}

    @property
    def is_started(self) -> bool:
        return self._is_started


@pytest.mark.asyncio
async def test_health_check_function_returns_expected_keys():
    payload = await health_check()
    for key in ["status", "service", "version", "environment", "db", "scraping", "openlibrary"]:
        assert key in payload


@pytest.mark.asyncio
async def test_root_function_returns_expected_payload():
    payload = await root()
    assert payload["docs"] == "/docs"
    assert "version" in payload


@pytest.mark.asyncio
async def test_global_exception_handler_returns_500_with_request_id_and_error_contract():
    request = SimpleNamespace(state=SimpleNamespace(request_id="abc-123"))
    response = await global_exception_handler(request, Exception("boom"))
    assert response.status_code == 500
    body = json.loads(response.body.decode("utf-8"))
    assert body["request_id"] == "abc-123"
    assert body["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert body["error"]["message"] == "Internal server error"


@pytest.mark.asyncio
async def test_standard_scraping_exception_handler_logs_request_context(monkeypatch: pytest.MonkeyPatch):
    request = SimpleNamespace(
        state=SimpleNamespace(request_id="req-123"),
        method="POST",
        url=SimpleNamespace(path="/api/v1/catalog/books"),
    )
    exc = ScrapingError(
        "Unable to extract authors from www.buscalibre.com.co page",
        reason="authors_not_found",
        diagnostics={"field_name": "authors", "attempted_sources": 2},
    )
    captured: dict[str, object] = {}

    def fake_warning(message: str, *, extra: dict[str, object]) -> None:
        captured["message"] = message
        captured["extra"] = extra

    monkeypatch.setattr(root_app_module.logger, "warning", fake_warning)
    response = await standard_exception_handler(request, exc)

    body = json.loads(response.body.decode("utf-8"))
    assert response.status_code == 400
    assert body["request_id"] == "req-123"
    assert body["error"]["code"] == "SCRAPING_ERROR"
    assert captured["message"] == "Scraping request failed"
    assert captured["extra"] == {
        "request_id": "req-123",
        "method": "POST",
        "path": "/api/v1/catalog/books",
        "error_code": "SCRAPING_ERROR",
        "error_message": "Unable to extract authors from www.buscalibre.com.co page",
        "scraping_reason": "authors_not_found",
        "scraping_diagnostics": {"field_name": "authors", "attempted_sources": 2},
    }


@pytest.mark.asyncio
async def test_standard_scraping_exception_handler_sanitizes_proxy_credentials(monkeypatch: pytest.MonkeyPatch):
    request = SimpleNamespace(
        state=SimpleNamespace(request_id="req-999"),
        method="POST",
        url=SimpleNamespace(path="/api/v1/catalog/books"),
    )
    exc = ScrapingError(
        "HTTP runtime failed via http://user:pass@proxy.example:8080",
        reason="fetch_failed",
        diagnostics={
            "proxy_url": "http://user:pass@proxy.example:8080",
            "nested": ["http://user:pass@proxy.example:8080", {"proxy": "http://user:pass@proxy.example:8080"}],
        },
    )
    captured: dict[str, object] = {}

    def fake_warning(message: str, *, extra: dict[str, object]) -> None:
        captured["message"] = message
        captured["extra"] = extra

    monkeypatch.setattr(root_app_module.logger, "warning", fake_warning)

    response = await standard_exception_handler(request, exc)

    body = json.loads(response.body.decode("utf-8"))
    assert response.status_code == 400
    assert body["error"]["message"] == "HTTP runtime failed via http://***:***@proxy.example:8080"
    assert captured["message"] == "Scraping request failed"
    assert captured["extra"] == {
        "request_id": "req-999",
        "method": "POST",
        "path": "/api/v1/catalog/books",
        "error_code": "SCRAPING_ERROR",
        "error_message": "HTTP runtime failed via http://***:***@proxy.example:8080",
        "scraping_reason": "fetch_failed",
        "scraping_diagnostics": {
            "proxy_url": "http://***:***@proxy.example:8080",
            "nested": ["http://***:***@proxy.example:8080", {"proxy": "http://***:***@proxy.example:8080"}],
        },
    }


@pytest.mark.asyncio
async def test_lifespan_builds_selected_runtime_and_manages_lifecycle(monkeypatch: pytest.MonkeyPatch):
    bsentinel_pkg = importlib.import_module("bsentinel")
    settings_module = importlib.import_module("bsentinel._settings")
    scraping_module = importlib.import_module("bsentinel.infrastructure.scraping")
    runtime = RuntimeStub()
    scheduler_calls: list[tuple[str, object]] = []

    monkeypatch.setattr(scraping_module, "build_scraping_runtime", lambda runtime_settings: runtime)

    importlib.reload(settings_module)
    bsentinel_pkg.settings = settings_module.settings
    reloaded_module = importlib.reload(root_app_module)
    monkeypatch.setattr(
        reloaded_module.scheduler,
        "start",
        lambda *, interval_hours: scheduler_calls.append(("start", interval_hours)),
    )
    monkeypatch.setattr(
        reloaded_module.scheduler,
        "shutdown",
        lambda: scheduler_calls.append(("shutdown", None)),
    )

    async with AsyncExitStack() as stack:
        await stack.enter_async_context(reloaded_module.lifespan(reloaded_module.root_app))

        assert runtime.start_calls == 1
        assert reloaded_module.scraper_client._session is runtime
        assert reloaded_module.root_app.state.scraping_runtime is runtime
        assert scheduler_calls == [("start", reloaded_module.settings.scheduler_scrape_interval_hours)]

    assert runtime.close_calls == 1
    assert scheduler_calls == [
        ("start", reloaded_module.settings.scheduler_scrape_interval_hours),
        ("shutdown", None),
    ]
