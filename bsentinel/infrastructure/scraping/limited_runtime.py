"""One request budget shared by all store entry points in this process."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from bsentinel.infrastructure.scraping.store_guard import check_periodic_admission, fetch_admission

if TYPE_CHECKING:
    from bsentinel.infrastructure.scraping.runtime_factory import ScrapingRuntime


class LimitedRuntime:
    handles_store_admission = True

    def __init__(self, backend: ScrapingRuntime, concurrency: int = 3) -> None:
        if concurrency < 1:
            raise ValueError("concurrency must be positive")
        self.backend = backend
        self.concurrency = concurrency
        self._permits = asyncio.Semaphore(concurrency)
        self.active = 0
        self.peak_active = 0

    async def start(self) -> None:
        await self.backend.start()

    async def close(self) -> None:
        await self.backend.close()

    @property
    def is_started(self) -> bool:
        return self.backend.is_started

    @property
    def effective_config(self) -> dict[str, Any]:
        return getattr(self.backend, "effective_config", {})

    async def fetch(self, url: str) -> Any:
        # Includes the backend's retry loop; extractor retries re-enter this budget.
        check_periodic_admission()
        async with self._permits:
            self.active += 1
            self.peak_active = max(self.peak_active, self.active)
            try:
                check_periodic_admission()
                admission = fetch_admission.get()
                if admission is None:
                    return await self.backend.fetch(url)
                async with admission.guard.request(admission.store, admission.classify) as publish:
                    check_periodic_admission()
                    page = await self.backend.fetch(url)
                    await publish(page)
                    return page
            finally:
                self.active -= 1
