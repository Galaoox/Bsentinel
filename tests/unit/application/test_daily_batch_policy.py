from datetime import UTC, datetime
from unittest.mock import AsyncMock

from bsentinel.application.services.scraping_batch import ScrapingBatch
from bsentinel.domain.traffic import project_traffic
from bsentinel.infrastructure.scheduler import LocalScheduler


async def test_forced_batch_outside_window_makes_no_request_or_query():
    listing = AsyncMock(return_value=[])
    process = AsyncMock()
    summary = await ScrapingBatch(listing, process, clock=lambda: datetime(2026, 10, 8, 18, tzinfo=UTC)).run()
    assert summary.skipped_window is True
    listing.assert_not_called()
    process.assert_not_called()


async def test_timer_uses_absolute_colombia_cron_slots():
    scheduler = LocalScheduler(AsyncMock(return_value=0))
    try:
        scheduler.start()
        job = scheduler.scheduler.get_job('scrape_all')
        assert str(job.trigger.timezone) == 'America/Bogota'
        assert str(job.trigger.fields[5]) == '8,17'
        assert str(job.trigger.fields[6]) == '0,20,40'
        assert job.max_instances == 1
        assert job.coalesce is True
        assert job.misfire_grace_time == 119
        import asyncio
        await asyncio.sleep(0)
        scheduler.run_scraping_batch.assert_not_called()
        from zoneinfo import ZoneInfo
        bogota = ZoneInfo('America/Bogota')
        # Restart after noon goes to 17:00, not start-time + 20 minutes.
        assert job.trigger.get_next_fire_time(None, datetime(2026, 10, 8, 13, 7, tzinfo=bogota)) == datetime(2026, 10, 8, 17, tzinfo=bogota)
        # Restart mid-window does not replay the missed group-zero wakeup.
        assert job.trigger.get_next_fire_time(None, datetime(2026, 10, 8, 8, 0, 30, tzinfo=bogota)) == datetime(2026, 10, 8, 8, 20, tzinfo=bogota)
    finally:
        await scheduler.aclose()


def test_projection_uses_two_daily_reviews_not_hourly():
    projection = project_traffic(sample_operations=1, mean_bytes=100, relation_count=10, relation_count_source='requested')
    assert projection['bytes_24h'] == 2000
    assert projection['bytes_30d'] == 60000
    assert projection['scheduled_reviews_per_relation_day'] == 2
    assert any('manual' in text and 'catalog' in text for text in projection['assumptions'])
