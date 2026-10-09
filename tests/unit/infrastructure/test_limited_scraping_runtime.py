import asyncio
from types import SimpleNamespace

import pytest

from bsentinel.infrastructure.scraping import runtime_factory


class BlockingRuntime:
    effective_config = {"profile": "fixture"}
    is_started = False

    def __init__(self):
        self.active = 0
        self.peak = 0
        self.ready = asyncio.Event()
        self.release = asyncio.Event()

    async def start(self):
        self.is_started = True

    async def close(self):
        self.is_started = False

    async def fetch(self, url):
        self.active += 1
        self.peak = max(self.peak, self.active)
        if self.active == 3:
            self.ready.set()
        try:
            await self.release.wait()
            if url == "error":
                raise RuntimeError("fixture")
            return url
        finally:
            self.active -= 1


async def test_factory_shares_three_permits_across_manual_import_periodic(monkeypatch):
    backend = BlockingRuntime()
    monkeypatch.setattr(runtime_factory, "HttpFetcherSession", lambda **kwargs: backend)
    settings = SimpleNamespace(
        scraping_runtime="http",
        scraping_http_timeout=30,
        scraping_http_retries=2,
        scraping_concurrency=3,
    )
    runtime = runtime_factory.build_scraping_runtime(settings)
    await runtime.start()
    tasks = [asyncio.create_task(runtime.fetch(str(i))) for i in range(12)]
    await asyncio.wait_for(backend.ready.wait(), 1)
    await asyncio.sleep(0)
    assert backend.peak == 3
    backend.release.set()
    assert await asyncio.gather(*tasks) == list(map(str, range(12)))
    assert runtime.effective_config == backend.effective_config
    await runtime.close()
    assert not runtime.is_started


async def test_cancel_and_failure_release_permits(monkeypatch):
    from bsentinel.infrastructure.scraping.limited_runtime import LimitedRuntime

    backend = BlockingRuntime()
    runtime = LimitedRuntime(backend, concurrency=3)
    tasks = [asyncio.create_task(runtime.fetch("blocked")) for _ in range(3)]
    await backend.ready.wait()
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    backend.release.set()
    with pytest.raises(RuntimeError):
        await runtime.fetch("error")
    assert await asyncio.wait_for(runtime.fetch("ok"), 1) == "ok"
    assert runtime.peak_active == 3
    assert runtime.active == 0
