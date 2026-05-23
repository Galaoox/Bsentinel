from types import SimpleNamespace

import pytest

from bsentinel.infrastructure.scraping.browser import StealthBrowserSession
from bsentinel.infrastructure.scraping.http_fetcher import HttpFetcherSession
from bsentinel.infrastructure.scraping.runtime_factory import build_scraping_runtime


def test_build_scraping_runtime_defaults_to_http():
    settings = SimpleNamespace(
        scraping_http_timeout=20,
        scraping_http_retries=5,
        scraping_http_impersonate="chrome",
        scraping_http_http3=True,
        scraping_http_stealthy_headers=False,
        scraping_http_proxy="http://user:pass@proxy.example:8080",
    )

    runtime = build_scraping_runtime(settings)

    assert isinstance(runtime, HttpFetcherSession)


def test_build_scraping_runtime_uses_browser_when_explicitly_configured():
    settings = SimpleNamespace(
        scraping_runtime="browser",
        scraping_browser_headless=True,
        scraping_browser_timeout_ms=45000,
        scraping_browser_max_pages=3,
        scraping_browser_disable_resources=True,
        scraping_browser_network_idle=True,
        scraping_browser_solve_cloudflare=False,
        scraping_browser_real_chrome=False,
    )

    runtime = build_scraping_runtime(settings)

    assert isinstance(runtime, StealthBrowserSession)


def test_build_scraping_runtime_rejects_invalid_runtime():
    settings = SimpleNamespace(scraping_runtime="stealth")

    with pytest.raises(ValueError, match="Invalid scraping runtime"):
        build_scraping_runtime(settings)
