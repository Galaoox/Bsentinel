import importlib
import sqlite3

import pytest

from bsentinel._settings import Settings
from bsentinel.infrastructure.scraping.configured import ConfiguredStoreScraper


def test_cooldown_configuration_default_and_validation():
    assert Settings(_env_file=None).scraping_block_cooldown_minutes == 60
    with pytest.raises(ValueError):
        Settings(_env_file=None, scraping_block_cooldown_minutes=0)


@pytest.mark.parametrize('bulk', [False, True])
def test_public_catalog_block_is_persisted_after_rollback_no_retry_or_fake_traffic(client, monkeypatch, bulk):
    from curl_cffi import CurlInfo
    from curl_cffi.requests import AsyncSession, Response

    from bsentinel.infrastructure.scraping.http_fetcher import HttpFetcherSession
    from bsentinel.infrastructure.scraping.limited_runtime import LimitedRuntime
    app = importlib.import_module('bsentinel.infrastructure.api.root_app')
    events, sessions = [], []
    async def sink(event):
        events.append(event)
    async def request(self, method, **kwargs):
        sessions.append(id(self))
        result = Response()
        result.url = kwargs['url']
        result.content = b'<html><title>Human Verification</title></html>'
        result.status_code, result.reason = 405, 'fixture'
        result.headers = {'X-Amzn-Waf-Action': 'CaPtChA', 'Content-Type': 'text/html'}
        result.infos = {CurlInfo.SIZE_DOWNLOAD_T: 44, CurlInfo.SIZE_UPLOAD_T: 0,
                        CurlInfo.REQUEST_SIZE: 90, CurlInfo.HEADER_SIZE: 40, CurlInfo.REDIRECT_COUNT: 0}
        return result
    monkeypatch.setattr(AsyncSession, 'request', request)
    runtime = LimitedRuntime(HttpFetcherSession(timeout=1, retries=2, traffic_sink=sink))
    client.portal.call(runtime.start)
    monkeypatch.setattr(app, 'scraper_client', ConfiguredStoreScraper(runtime, store_guard=app.store_guard))
    login = client.post('/api/v1/auth/login', data={'username': 'admin', 'password': 'changeme'})
    headers = {'Authorization': 'Bearer ' + login.json()['access_token']}
    url = 'https://www.buscalibre.com.co/fixture-book'
    route = '/api/v1/catalog/books' + ('/bulk' if bulk else '')
    try:
        first = client.post(route, json={'urls': [url]} if bulk else {'url': url}, headers=headers)
        second = client.post('/api/v1/catalog/books', json={'url': url}, headers=headers)
    finally:
        client.portal.call(runtime.close)
    assert first.status_code == second.status_code == 400
    assert first.json()['error']['details']['scraping_reason'] == 'captcha_blocked'
    assert second.json()['error']['details']['scraping_reason'] == 'store_paused'
    assert len(sessions) == len(events) == 1
    assert events[0].http_status == 405
    assert events[0].download_bytes == 44
    assert events[0].outcome == 'http_error'
    path = app.settings.database_url.removeprefix('sqlite+aiosqlite:///')
    assert 'bsentinel-test-' in path
    with sqlite3.connect(f'file:{path}?mode=ro', uri=True) as conn:
        assert conn.execute('SELECT COUNT(*) FROM books').fetchone()[0] == 0
        assert conn.execute('SELECT COUNT(*) FROM price_history').fetchone()[0] == 0
        assert conn.execute('SELECT reason FROM scraping_store_blocks').fetchone()[0] == 'captcha_blocked'
