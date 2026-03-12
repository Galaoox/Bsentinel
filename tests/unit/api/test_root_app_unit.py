import importlib
import json
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
