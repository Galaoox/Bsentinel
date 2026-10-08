import asyncio
from unittest.mock import AsyncMock

import pytest

from bsentinel._settings import Settings
from bsentinel.infrastructure.scheduler import LocalScheduler


@pytest.mark.asyncio
async def test_legacy_interval_argument_cannot_override_daily_policy(monkeypatch):
    monkeypatch.setenv("SCHEDULER_SCRAPE_INTERVAL_HOURS", "0.016666666666666666")
    settings = Settings(_env_file=None)
    run_batch = AsyncMock(return_value=0)
    scheduler = LocalScheduler(run_batch)

    try:
        scheduler.start(interval_hours=settings.scheduler_scrape_interval_hours)

        job = scheduler.scheduler.get_job("scrape_all")
        assert str(job.trigger.fields[5]) == "8,17"
        run_batch.assert_not_called()
    finally:
        scheduler.shutdown()


async def test_absolute_cohort_cron_is_coalesced_and_single_instance():
    scheduler = LocalScheduler(AsyncMock(return_value=0))
    try:
        scheduler.start(tick_minutes=20)
        job = scheduler.scheduler.get_job('scrape_all')
        assert str(job.trigger.fields[6]) == "0,20,40"
        assert job.max_instances == 1
        assert job.coalesce is True
    finally:
        await scheduler.aclose()


async def test_manual_and_automatic_share_guard_shutdown_awaits_cancellation():
    entered = asyncio.Event()
    cancelled = asyncio.Event()
    calls = 0
    async def run():
        nonlocal calls
        calls += 1
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()
    scheduler = LocalScheduler(run)
    scheduler.trigger_now()
    await entered.wait()
    await asyncio.wait_for(scheduler._run_scraping(), .1)
    for _ in range(20):
        scheduler.trigger_now()
    await asyncio.sleep(0)
    assert calls == 1
    await scheduler.aclose()
    assert cancelled.is_set()
    assert not scheduler._tasks
