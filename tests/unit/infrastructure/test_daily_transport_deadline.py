import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from bsentinel.domain.models import Store
from bsentinel.domain.scraping_schedule import current_slot
from bsentinel.exceptions import ScrapingError
from bsentinel.infrastructure.scraping.store_guard import (
    Admission,
    StoreGuard,
    fetch_admission,
    periodic_admission,
)
from bsentinel.infrastructure.scraping.traffic import instrument_transport


@pytest.mark.parametrize("hour,group", [(13, 0), (13, 1), (13, 2), (22, 0), (22, 1), (22, 2)])
async def test_transport_rechecks_clock_after_awaited_store_read(hour, group):
    slot = datetime(2026, 10, 8, hour, group * 20, tzinfo=UTC)
    now = [slot + timedelta(minutes=19, seconds=59)]
    calls, events = [], []

    class Persistence:
        async def read(self, store_id):
            await asyncio.sleep(0)
            now[0] += timedelta(seconds=2)
            return None

    async def request(*args, **kwargs):
        calls.append(now[0])
        return SimpleNamespace(status_code=200, infos={})

    async def sink(event):
        events.append(event)

    transport = SimpleNamespace(request=request, curl_infos=[])
    instrument_transport(SimpleNamespace(_async_curl_session=transport), sink)
    a = fetch_admission.set(
        Admission(StoreGuard(Persistence()), Store(domain="fixture.invalid"), None)
    )
    b = periodic_admission.set(lambda: current_slot(group, now[0]) == slot)
    try:
        try:
            await transport.request("GET", url="https://fixture.invalid/book")
        except ScrapingError as exc:
            assert exc.reason == "schedule_skipped"
    finally:
        fetch_admission.reset(a)
        periodic_admission.reset(b)
    assert not calls, "No HTTP may begin after the cohort deadline during SQL read"
    assert not events, "Admission rejection must not fabricate traffic"


@pytest.mark.parametrize("half_open", [False, True])
async def test_runtime_rechecks_after_guard_read_and_releases_probe(half_open):
    from bsentinel.infrastructure.scraping.limited_runtime import LimitedRuntime
    from bsentinel.infrastructure.scraping.store_guard import BlockState, MemoryBlockPersistence

    slot = datetime(2026, 10, 8, 13, tzinfo=UTC)
    now = [slot + timedelta(minutes=19, seconds=59)]
    store = Store(domain="fixture.invalid")

    class Persistence(MemoryBlockPersistence):
        async def read(self, store_id):
            result = await super().read(store_id)
            now[0] += timedelta(seconds=2)
            return result

    persistence = Persistence()
    if half_open:
        await persistence.extend(store.id, BlockState(slot, "captcha_blocked"))
    guard = StoreGuard(persistence, clock=lambda: now[0])
    calls = []

    async def fetch(url):
        calls.append(url)
        return object()

    runtime = LimitedRuntime(SimpleNamespace(fetch=fetch))
    a = fetch_admission.set(Admission(guard, store, lambda *args: SimpleNamespace(kind="usable")))
    b = periodic_admission.set(lambda: current_slot(0, now[0]) == slot)
    try:
        try:
            await runtime.fetch("https://fixture.invalid/book")
        except ScrapingError as exc:
            assert exc.reason == "schedule_skipped"
    finally:
        fetch_admission.reset(a)
        periodic_admission.reset(b)
    assert not calls
    assert runtime.active == 0
    assert runtime._permits._value == 3
    assert not guard.entries


async def test_expired_work_rejects_before_waiting_for_occupied_permit():
    from bsentinel.infrastructure.scraping.limited_runtime import LimitedRuntime

    runtime = LimitedRuntime(SimpleNamespace(), concurrency=1)
    await runtime._permits.acquire()
    token = periodic_admission.set(lambda: False)
    try:
        with pytest.raises(ScrapingError) as caught:
            await asyncio.wait_for(runtime.fetch("https://fixture.invalid/book"), 0.05)
        assert caught.value.reason == "schedule_skipped"
    finally:
        periodic_admission.reset(token)
        runtime._permits.release()


async def test_real_curl_retry_loop_stops_at_cohort_deadline(monkeypatch):
    from curl_cffi.requests import AsyncSession
    from curl_cffi.requests.exceptions import Timeout

    from bsentinel.infrastructure.scraping.configured import ConfiguredStoreScraper
    from bsentinel.infrastructure.scraping.http_fetcher import HttpFetcherSession
    from bsentinel.infrastructure.scraping.limited_runtime import LimitedRuntime
    from bsentinel.infrastructure.scraping.store_guard import MemoryBlockPersistence

    slot = datetime(2026, 10, 8, 13, tzinfo=UTC)
    now = [slot + timedelta(minutes=19, seconds=59)]
    calls, events = [], []

    async def request(self, method, **kwargs):
        calls.append(now[0])
        now[0] += timedelta(seconds=2)
        raise Timeout("offline fixture", 28)

    async def sink(event):
        events.append(event)

    monkeypatch.setattr(AsyncSession, "request", request)
    backend = HttpFetcherSession(timeout=1, retries=2, traffic_sink=sink)
    backend._config["retry_delay"] = 0
    runtime = LimitedRuntime(backend)
    await runtime.start()
    token = periodic_admission.set(lambda: current_slot(0, now[0]) == slot)
    try:
        with pytest.raises(ScrapingError) as caught:
            await ConfiguredStoreScraper(
                runtime, store_guard=StoreGuard(MemoryBlockPersistence())
            ).scrape_book(Store(domain="fixture.invalid"), "https://fixture.invalid/book")
        assert caught.value.reason == "schedule_skipped"
    finally:
        periodic_admission.reset(token)
        await runtime.close()
    assert len(calls) == len(events) == 1
    assert events[0].outcome == "failed"
    assert runtime.active == 0


async def test_expired_attempt_rejects_before_store_guard_database_read():
    reads = []

    class Persistence:
        async def read(self, store_id):
            reads.append(store_id)
            return None

    token = periodic_admission.set(lambda: False)
    try:
        with pytest.raises(ScrapingError) as caught:
            await StoreGuard(Persistence()).check(Store(domain='fixture.invalid'))
        assert caught.value.reason == 'schedule_skipped'
    finally:
        periodic_admission.reset(token)
    assert not reads
