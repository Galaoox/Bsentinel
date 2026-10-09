from types import SimpleNamespace

import pytest

from bsentinel.infrastructure.scraping.browser import StealthBrowserSession
from bsentinel.infrastructure.scraping.http_fetcher import HttpFetcherSession
from bsentinel.infrastructure.scraping.runtime_factory import build_scraping_runtime


def test_build_scraping_runtime_defaults_to_http():
    settings = SimpleNamespace(
        scraping_http_timeout=20,
        scraping_http_retries=5,
        scraping_http_profile="chrome_stable",
        scraping_http_impersonate="chrome",
        scraping_http_http3=True,
        scraping_http_stealthy_headers=False,
        scraping_http_proxy="http://user:pass@proxy.example:8080",
    )

    runtime = build_scraping_runtime(settings)

    assert isinstance(runtime.backend, HttpFetcherSession)
    assert runtime.effective_config == {
        "profile": "chrome_stable",
        "timeout": 20,
        "retries": 5,
        "impersonate": "chrome",
        "http3": True,
        "stealthy_headers": False,
        "proxy": "http://user:pass@proxy.example:8080",
    }


def test_build_scraping_runtime_uses_http_profile_defaults_when_overrides_are_missing():
    settings = SimpleNamespace(
        scraping_http_timeout=30,
        scraping_http_retries=2,
        scraping_http_profile="firefox_stable",
        scraping_http_proxy=None,
    )

    runtime = build_scraping_runtime(settings)

    assert isinstance(runtime.backend, HttpFetcherSession)
    assert runtime.effective_config == {
        "profile": "firefox_stable",
        "timeout": 30,
        "retries": 2,
        "impersonate": "firefox",
        "http3": False,
        "stealthy_headers": True,
        "proxy": None,
    }


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

    assert isinstance(runtime.backend, StealthBrowserSession)


def test_build_scraping_runtime_rejects_invalid_runtime():
    settings = SimpleNamespace(scraping_runtime="stealth")

    with pytest.raises(ValueError, match="Invalid scraping runtime"):
        build_scraping_runtime(settings)


def test_browser_with_configured_http_proxy_is_rejected_without_constructing_browser(monkeypatch):
    from bsentinel.infrastructure.scraping import runtime_factory

    def forbidden_browser(**kwargs):
        pytest.fail("Browser constructed despite unsupported configured proxy")

    monkeypatch.setattr(runtime_factory, "StealthBrowserSession", forbidden_browser)
    settings = SimpleNamespace(scraping_runtime="browser", scraping_http_proxy="http://proxy.fixture.invalid:8080",
                               scraping_browser_headless=True, scraping_browser_timeout_ms=3000,
                               scraping_browser_max_pages=1, scraping_browser_disable_resources=True,
                               scraping_browser_network_idle=False, scraping_browser_solve_cloudflare=False,
                               scraping_browser_real_chrome=False)
    with pytest.raises(ValueError, match="Browser runtime does not support the configured proxy"):
        build_scraping_runtime(settings)
