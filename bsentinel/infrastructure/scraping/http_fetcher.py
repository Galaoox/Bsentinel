"""HTTP-first Scrapling session runtime."""

from __future__ import annotations

from typing import Any

from curl_cffi.curl import CurlError
from scrapling.fetchers import FetcherSession

from bsentinel.exceptions import ScrapingError
from bsentinel.infrastructure.scraping.sanitization import sanitize_proxy_credentials
from bsentinel.infrastructure.scraping.traffic import discard_event, instrument_transport


class HttpFetcherSession:
    def __init__(
        self,
        *,
        timeout: int,
        retries: int,
        profile: str = "chrome_stable",
        impersonate: str | None = None,
        http3: bool = False,
        stealthy_headers: bool = True,
        proxy: str | None = None,
        traffic_sink=discard_event,
    ) -> None:
        self.traffic_sink = traffic_sink
        self._effective_config = {
            "profile": profile,
            "timeout": timeout,
            "retries": retries,
            "impersonate": impersonate or "chrome",
            "http3": http3,
            "stealthy_headers": stealthy_headers,
            "proxy": proxy,
        }
        self._config = {
            key: value for key, value in self._effective_config.items() if key != "profile"
        }
        self._manager: FetcherSession | None = None
        self._session: Any | None = None

    async def start(self) -> None:
        if self._session is not None:
            return
        manager = FetcherSession(**self._config)
        self._session = await manager.__aenter__()
        self._manager = manager

    async def close(self) -> None:
        if self._manager is None:
            return
        try:
            await self._manager.__aexit__(None, None, None)
        finally:
            self._manager = None
            self._session = None

    async def fetch(self, url: str):
        if self._session is None:
            raise RuntimeError("HTTP fetcher session is not initialized")
        try:
            # Installed Scrapling warns against concurrent use of one curl session.
            # Each request owns its response/cookies/impersonation state and retry loop.
            async with FetcherSession(**self._config) as session:
                instrument_transport(session, self.traffic_sink)
                # Scrapling 0.4.2 merges an omitted request proxy as explicit None,
                # overriding the session default. Never rely on that default.
                request_options = {"proxy": self._config["proxy"]} if self._config["proxy"] else {}
                return await session.get(url, **request_options)
        except (CurlError, TimeoutError) as exc:
            raise ScrapingError(
                sanitize_proxy_credentials(str(exc)), reason="fetch_failed",
                diagnostics={"error_type": type(exc).__name__},
            ) from exc

    @property
    def is_started(self) -> bool:
        return self._session is not None

    @property
    def effective_config(self) -> dict[str, Any]:
        return dict(self._effective_config)
