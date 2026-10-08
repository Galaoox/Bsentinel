"""Runtime selection for scraping sessions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from bsentinel.infrastructure.scraping.browser import StealthBrowserSession
from bsentinel.infrastructure.scraping.http_fetcher import HttpFetcherSession


@dataclass(frozen=True, slots=True)
class HttpProfile:
    name: str
    impersonate: str
    http3: bool
    stealthy_headers: bool


HTTP_PROFILES = {
    "chrome_stable": HttpProfile(
        name="chrome_stable",
        impersonate="chrome",
        http3=False,
        stealthy_headers=True,
    ),
    "firefox_stable": HttpProfile(
        name="firefox_stable",
        impersonate="firefox",
        http3=False,
        stealthy_headers=True,
    ),
}


def _resolve_http_profile(settings: object) -> HttpProfile:
    profile_name = getattr(settings, "scraping_http_profile", "chrome_stable")
    return HTTP_PROFILES.get(profile_name, HTTP_PROFILES["chrome_stable"])


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
        profile = _resolve_http_profile(settings)
        return HttpFetcherSession(
            timeout=getattr(settings, "scraping_http_timeout"),
            retries=getattr(settings, "scraping_http_retries"),
            profile=profile.name,
            impersonate=getattr(
                settings, "scraping_http_impersonate", None) or profile.impersonate,
            http3=getattr(settings, "scraping_http_http3", profile.http3),
            stealthy_headers=getattr(
                settings, "scraping_http_stealthy_headers", profile.stealthy_headers),
            proxy=getattr(settings, "scraping_http_proxy", None),
        )

    if runtime == "browser":
        return StealthBrowserSession(
            headless=getattr(settings, "scraping_browser_headless"),
            timeout_ms=getattr(settings, "scraping_browser_timeout_ms"),
            max_pages=getattr(settings, "scraping_browser_max_pages"),
            disable_resources=getattr(
                settings, "scraping_browser_disable_resources"),
            network_idle=getattr(settings, "scraping_browser_network_idle"),
            solve_cloudflare=getattr(
                settings, "scraping_browser_solve_cloudflare"),
            real_chrome=getattr(settings, "scraping_browser_real_chrome"),
        )

    raise ValueError(f"Invalid scraping runtime: {runtime}")
