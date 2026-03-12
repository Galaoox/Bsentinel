"""Shared Scrapling browser session management."""

from __future__ import annotations

from scrapling.fetchers import AsyncStealthySession


class StealthBrowserSession:
    def __init__(
        self,
        *,
        headless: bool,
        timeout_ms: int,
        max_pages: int,
        disable_resources: bool,
        network_idle: bool,
        solve_cloudflare: bool,
        real_chrome: bool,
    ) -> None:
        self._headless = headless
        self._timeout_ms = timeout_ms
        self._max_pages = max_pages
        self._disable_resources = disable_resources
        self._network_idle = network_idle
        self._solve_cloudflare = solve_cloudflare
        self._real_chrome = real_chrome
        self._manager: AsyncStealthySession | None = None
        self._session: AsyncStealthySession | None = None

    async def start(self) -> None:
        if self._session is not None:
            return
        manager = AsyncStealthySession(
            headless=self._headless,
            timeout=self._timeout_ms,
            max_pages=self._max_pages,
            disable_resources=self._disable_resources,
            network_idle=self._network_idle,
            solve_cloudflare=self._solve_cloudflare,
            real_chrome=self._real_chrome,
            block_webrtc=True,
            hide_canvas=True,
        )
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
            raise RuntimeError("Stealth browser session is not initialized")
        return await self._session.fetch(url)

    @property
    def is_started(self) -> bool:
        return self._session is not None
