from datetime import timedelta
from unittest.mock import AsyncMock

import pytest

from bsentinel._settings import Settings
from bsentinel.infrastructure.scheduler import LocalScheduler


@pytest.mark.asyncio
async def test_scheduler_accepts_one_minute_interval_from_environment(monkeypatch):
    monkeypatch.setenv("SCHEDULER_SCRAPE_INTERVAL_HOURS", "0.016666666666666666")
    settings = Settings(_env_file=None)
    run_batch = AsyncMock(return_value=0)
    scheduler = LocalScheduler(run_batch)

    try:
        scheduler.start(interval_hours=settings.scheduler_scrape_interval_hours)

        job = scheduler.scheduler.get_job("scrape_all")
        assert job.trigger.interval == timedelta(minutes=1)
        run_batch.assert_not_called()
    finally:
        scheduler.shutdown()
