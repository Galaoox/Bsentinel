import json
from types import SimpleNamespace

import pytest

from bsentinel.infrastructure.api.root_app import global_exception_handler, health_check, root


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
