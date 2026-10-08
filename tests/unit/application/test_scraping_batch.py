import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID


async def test_three_workers_process_hundreds_once_with_isolated_errors():
    from bsentinel.application.services.scraping_batch import ScrapingBatch
    from bsentinel.domain.models import BookStoreRelation

    now = datetime(2026, 10, 8, 13, tzinfo=UTC)
    rows = [
        BookStoreRelation(
            id=UUID(int=i + 1), scrape_group=i % 3, next_check_at=now - timedelta(hours=1)
        )
        for i in range(303)
    ]
    active = peak = 0
    seen = []

    async def page(cutoff, limit, after):
        return [
            r
            for r in rows
            if after is None or (r.next_check_at, str(r.id)) > (after[0], str(after[1]))
        ][:limit]

    async def process(row, cutoff):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        try:
            await asyncio.sleep(0.001)
            seen.append(row.id)
            if row.id.int % 11 == 0:
                raise RuntimeError("isolated fixture error")
            return "successful"
        finally:
            active -= 1

    batch = ScrapingBatch(page, process, clock=lambda: now, page_size=15)
    summaries = []
    for group in range(3):
        now = now.replace(minute=group * 20)
        summaries.append(await batch.run())
    assert sum(summary.selected for summary in summaries) == 303
    assert sum(summary.failed for summary in summaries) == 27
    assert sum(summary.successful for summary in summaries) == 276
    assert len(set(seen)) == 303
    assert peak == 3
    assert batch.peak_queue <= 6
    assert [summary.max_lateness_seconds for summary in summaries] == [3600, 4800, 6000]


async def test_overlapping_batch_is_skipped_and_cancel_drains_workers():
    from bsentinel.application.services.scraping_batch import ScrapingBatch
    from bsentinel.domain.models import BookStoreRelation

    now = datetime(2026, 10, 8, 13, tzinfo=UTC)
    row = BookStoreRelation(next_check_at=now, scrape_group=0)
    ready = asyncio.Event()
    cancelled = asyncio.Event()

    async def page(cutoff, limit, after):
        return [row] if after is None else []

    async def process(row, cutoff):
        ready.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    batch = ScrapingBatch(page, process, clock=lambda: now)
    task = asyncio.create_task(batch.run())
    await ready.wait()
    assert (await batch.run()).skipped_overlap
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    assert cancelled.is_set()
    assert not batch.running
