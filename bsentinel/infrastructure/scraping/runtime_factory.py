"""Runtime selection for scraping sessions."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from bsentinel.infrastructure.scraping.browser import StealthBrowserSession
from bsentinel.infrastructure.scraping.http_fetcher import HttpFetcherSession


@runtime_checkable
class ScrapingRuntime(Protocol):
    async def start(self) -> None: ...
    async def close(self) -> None: ...
    async def fetch(self, url: str): ...

    @property
    def is_started(self) -> bool: ...


def build_scraping_runtime(settings: object) -> ScrapingRuntime:
    runtime = getattr(settings, "scraping_runtime", "http")

    if runtime == "http":
        return HttpFetcherSession(
            timeout=getattr(settings, "scraping_http_timeout"),
            retries=getattr(settings, "scraping_http_retries"),
            impersonate=getattr(settings, "scraping_http_impersonate", None),
            http3=getattr(settings, "scraping_http_http3", False),
            stealthy_headers=getattr(settings, "scraping_http_stealthy_headers", True),
            proxy=getattr(settings, "scraping_http_proxy", None),
        )

    if runtime == "browser":
        return StealthBrowserSession(
            headless=getattr(settings, "scraping_browser_headless"),
            timeout_ms=getattr(settings, "scraping_browser_timeout_ms"),
            max_pages=getattr(settings, "scraping_browser_max_pages"),
            disable_resources=getattr(settings, "scraping_browser_disable_resources"),
            network_idle=getattr(settings, "scraping_browser_network_idle"),
            solve_cloudflare=getattr(settings, "scraping_browser_solve_cloudflare"),
            real_chrome=getattr(settings, "scraping_browser_real_chrome"),
        )

    raise ValueError(f"Invalid scraping runtime: {runtime}")
