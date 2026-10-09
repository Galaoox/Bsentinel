import asyncio
from types import SimpleNamespace

import pytest
from curl_cffi import CurlInfo


@pytest.mark.asyncio
async def test_transport_records_compressed_bytes_not_decoded_body():
    from bsentinel.infrastructure.scraping.traffic import instrument_transport

    events = []

    async def sink(event):
        events.append(event)

    async def request(*args, **kwargs):
        return SimpleNamespace(
            infos={
                CurlInfo.SIZE_DOWNLOAD_T: 20,
                CurlInfo.SIZE_UPLOAD_T: 0,
                CurlInfo.REQUEST_SIZE: 100,
                CurlInfo.HEADER_SIZE: 40,
                CurlInfo.REDIRECT_COUNT: 0,
            },
            content=b"x" * 200,
            status_code=200,
        )

    transport = SimpleNamespace(request=request, curl_infos=[])
    instrument_transport(SimpleNamespace(_async_curl_session=transport), sink)
    result = await transport.request("GET", url="https://shop.invalid/a?secret=hidden")
    assert len(result.content) == 200
    assert events[0].download_bytes == 20
    assert events[0].request_bytes == 100
    assert events[0].header_bytes == 40
    assert events[0].completeness == "known"
    assert events[0].domain == "shop.invalid"
    assert "hidden" not in str(events[0])
    assert CurlInfo.SIZE_DOWNLOAD_T in transport.curl_infos


@pytest.mark.asyncio
async def test_installed_scrapling_retry_hook_and_proxy(monkeypatch):
    from curl_cffi.requests import AsyncSession, Response
    from curl_cffi.requests.exceptions import Timeout

    from bsentinel.infrastructure.scraping.http_fetcher import HttpFetcherSession

    events, proxies = [], []

    async def sink(event):
        events.append(event)

    async def request(self, method, **kwargs):
        proxies.append(kwargs.get("proxy"))
        r = Response()
        r.url = kwargs["url"]
        r.content = b"<html>ok</html>"
        r.status_code = 200
        r.reason = "OK"
        r.infos = {
            CurlInfo.SIZE_DOWNLOAD_T: 14,
            CurlInfo.SIZE_UPLOAD_T: 0,
            CurlInfo.REQUEST_SIZE: 100,
            CurlInfo.HEADER_SIZE: 40,
            CurlInfo.REDIRECT_COUNT: 0,
        }
        if len(proxies) == 1:
            raise Timeout("fixture", 28, r)
        return r

    monkeypatch.setattr(AsyncSession, "request", request)
    fetcher = HttpFetcherSession(
        timeout=1, retries=2, proxy="http://fixture.invalid:8080", traffic_sink=sink
    )
    await fetcher.start()
    try:
        await fetcher.fetch("https://shop.invalid/private")
    finally:
        await fetcher.close()
    assert proxies == ["http://fixture.invalid:8080"] * 2
    assert [e.outcome for e in events] == ["failed", "successful"]
    assert all(e.download_bytes == 14 for e in events)


@pytest.mark.asyncio
async def test_cancel_and_missing_counters_are_unknown():
    from bsentinel.infrastructure.scraping.traffic import instrument_transport

    events = []

    async def sink(event):
        events.append(event)

    async def request(*args, **kwargs):
        raise asyncio.CancelledError

    transport = SimpleNamespace(request=request, curl_infos=[])
    instrument_transport(SimpleNamespace(_async_curl_session=transport), sink)
    with pytest.raises(asyncio.CancelledError):
        await transport.request("GET", url="https://shop.invalid/")
    assert events[0].outcome == "cancelled"
    assert events[0].completeness == "unknown"
    assert events[0].download_bytes is None


@pytest.mark.asyncio
async def test_sink_failure_is_counted_without_aborting_request(caplog):
    from bsentinel.infrastructure.scraping import traffic

    before = traffic.missing_writes

    async def sink(event):
        raise RuntimeError("private fixture message")

    async def request(*args, **kwargs):
        return SimpleNamespace(infos={}, status_code=200)

    transport = SimpleNamespace(request=request, curl_infos=[])
    traffic.instrument_transport(SimpleNamespace(_async_curl_session=transport), sink)
    await transport.request("GET", url="https://shop.invalid/private")
    assert traffic.missing_writes == before + 1
    assert "private fixture" not in caplog.text
    assert "Traffic persistence missing" in caplog.text


@pytest.mark.asyncio
async def test_redirects_and_partial_counters_are_incomplete():
    from bsentinel.infrastructure.scraping.traffic import instrument_transport

    events = []

    async def sink(event):
        events.append(event)

    async def request(*args, **kwargs):
        return SimpleNamespace(
            infos={CurlInfo.SIZE_DOWNLOAD_T: 20, CurlInfo.REDIRECT_COUNT: 2}, status_code=200
        )

    transport = SimpleNamespace(request=request, curl_infos=[])
    instrument_transport(SimpleNamespace(_async_curl_session=transport), sink)
    await transport.request("GET", url="https://shop.invalid/")
    assert events[0].completeness == "incomplete"
    assert events[0].request_bytes is None
    assert events[0].redirects == 2


@pytest.mark.asyncio
async def test_403_body_is_measured_but_not_successful():
    from bsentinel.infrastructure.scraping.traffic import instrument_transport

    events = []

    async def sink(event):
        events.append(event)

    async def request(*args, **kwargs):
        return SimpleNamespace(
            infos={
                CurlInfo.SIZE_DOWNLOAD_T: 520,
                CurlInfo.SIZE_UPLOAD_T: 0,
                CurlInfo.REQUEST_SIZE: 100,
                CurlInfo.HEADER_SIZE: 40,
                CurlInfo.REDIRECT_COUNT: 0,
            },
            status_code=403,
        )

    transport = SimpleNamespace(request=request, curl_infos=[])
    instrument_transport(SimpleNamespace(_async_curl_session=transport), sink)
    result = await transport.request("GET", url="https://shop.invalid/")
    assert result.status_code == 403
    assert events[0].http_status == 403
    assert events[0].outcome == "http_error"
    assert events[0].download_bytes == 520
    assert events[0].completeness == "known"


@pytest.mark.asyncio
async def test_ip_authority_is_not_recorded():
    from bsentinel.infrastructure.scraping.traffic import instrument_transport

    events = []

    async def sink(event):
        events.append(event)

    async def request(*args, **kwargs):
        return SimpleNamespace(infos={}, status_code=403)

    transport = SimpleNamespace(request=request, curl_infos=[])
    instrument_transport(SimpleNamespace(_async_curl_session=transport), sink)
    await transport.request("GET", url="http://192.0.2.1/private")
    assert events[0].domain == "unknown"


def test_missing_private_hook_reports_missing_coverage():
    from bsentinel.infrastructure.scraping import traffic

    before = traffic.unobserved_fetches
    assert traffic.instrument_transport(SimpleNamespace()) is False
    assert traffic.unobserved_fetches == before + 1


def test_installed_private_hook_contract():
    from importlib.metadata import version

    from curl_cffi.requests import AsyncSession
    from scrapling.engines.static import _ASyncSessionLogic

    assert version("scrapling") == "0.4.2"
    assert version("curl_cffi") == "0.14.0"
    assert "_async_curl_session" in _ASyncSessionLogic.__slots__
    assert callable(AsyncSession.request)
