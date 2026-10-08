from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from bsentinel.application.services.scraping_batch import ScrapingBatch
from bsentinel.domain.models import BookStoreRelation


@pytest.mark.parametrize("minute,second", [(2, 0), (13, 0), (19, 59)])
async def test_late_batch_start_does_not_replay_missed_cron(minute, second):
    listing = AsyncMock(return_value=[])
    batch = ScrapingBatch(
        listing, AsyncMock(), clock=lambda: datetime(2026, 10, 8, 13, minute, second, tzinfo=UTC)
    )
    assert (await batch.run()).skipped_window
    listing.assert_not_called()


async def test_batch_never_enqueues_another_cohort_even_when_overdue():
    now = datetime(2026, 10, 8, 13, tzinfo=UTC)
    rows = [BookStoreRelation(scrape_group=group, next_check_at=now) for group in range(3)]

    async def listing(cutoff, limit, after):
        return rows if after is None else []

    process = AsyncMock(return_value="successful")
    summary = await ScrapingBatch(listing, process, clock=lambda: now).run()
    assert summary.selected == summary.successful == 1
    assert [call.args[0].scrape_group for call in process.call_args_list] == [0]
