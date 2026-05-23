"""HTTP-first Scrapling session runtime."""

from __future__ import annotations

from typing import Any

from scrapling.fetchers import FetcherSession

from bsentinel.infrastructure.scraping.sanitization import sanitize_proxy_credentials


class HttpFetcherSession:
    def __init__(
        self,
        *,
        timeout: int,
        retries: int,
        impersonate: str | None = None,
        http3: bool = False,
        stealthy_headers: bool = True,
        proxy: str | None = None,
    ) -> None:
        self._config = {
            "timeout": timeout,
            "retries": retries,
            "impersonate": impersonate or "chrome",
            "http3": http3,
            "stealthy_headers": stealthy_headers,
            "proxy": proxy,
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
            return await self._session.get(url)
        except Exception as exc:
            sanitized_message = sanitize_proxy_credentials(str(exc))
            raise type(exc)(sanitized_message) from exc

    @property
    def is_started(self) -> bool:
        return self._session is not None
