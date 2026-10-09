"""Offline SQL/batch/transport regressions for immutable cohort identity."""

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from bsentinel.application.services.scraping_batch import ScrapingBatch
from bsentinel.domain.models import BookStoreRelation
from bsentinel.exceptions import ScrapingError
from bsentinel.infrastructure.persistence.scraping_batch import RelationProcessor
from bsentinel.infrastructure.persistence.sqlalchemy import (
    SQLBookRepository,
    SQLHistoryRepository,
    SQLRelationRepository,
    SQLStoreRepository,
)
from bsentinel.infrastructure.persistence.sqlalchemy.base import Base
from bsentinel.infrastructure.persistence.sqlalchemy.models import (
    BookModel,
    PriceHistoryModel,
    StoreModel,
)
from bsentinel.infrastructure.scraping.traffic import instrument_transport


@pytest.mark.parametrize("cutoff", [None, datetime(2026, 10, 8, 13)])
@pytest.mark.asyncio
async def test_periodic_cutoff_must_be_aware(cutoff):
    def no_context():
        raise AssertionError("invalid cutoff must be rejected before repository access")

    processor = RelationProcessor(no_context, SimpleNamespace())
    row = BookStoreRelation(scrape_group=0)
    with pytest.raises(ValueError, match="timezone-aware"):
        await processor.process(row, cutoff)


@pytest.mark.parametrize("resume", [
    datetime(2026, 10, 8, 22, 3, tzinfo=UTC),
    datetime(2026, 10, 9, 13, 1, tzinfo=UTC),
    datetime(2026, 10, 8, 13, 20, tzinfo=UTC),
])
@pytest.mark.asyncio
async def test_expired_cohort_never_adopts_later_slot(tmp_path, resume):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/cohort.db")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    start = datetime(2026, 10, 8, 13, tzinfo=UTC)
    now = [start]
    async with factory() as session, session.begin():
        session.add_all([
            BookModel(id=str(UUID(int=1000 + i)), title="fixture", created_at=start)
            for i in range(13)
        ] + [StoreModel(id=str(UUID(int=998)), name="fixture", domain="fixture.invalid",
                        country_code="CO", created_at=start)])

    @asynccontextmanager
    async def context():
        async with factory() as session, session.begin():
            yield SimpleNamespace(
                books=SQLBookRepository(session), stores=SQLStoreRepository(session),
                relations=SQLRelationRepository(session), history=SQLHistoryRepository(session),
            )

    # Overdue due timestamps are NOT the current batch's authorized slot.
    rows = [BookStoreRelation(
        id=UUID(int=i + 1), book_id=UUID(int=1000 + i), store_id=UUID(int=998),
        product_url=f"https://fixture.invalid/{i}", scrape_group=0 if i < 12 else 1,
        next_check_at=start - timedelta(days=1), current_price=12,
    ) for i in range(13)]
    async with context() as repos:
        for row in rows:
            await repos.relations.add(row)
    calls, events, rejected_retries = [], [], []

    async def request(method, **kwargs):
        calls.append((kwargs["url"], now[0]))
        now[0] = resume
        await asyncio.sleep(0)
        return SimpleNamespace(status_code=200, infos={})

    async def sink(event):
        events.append(event)

    transport = SimpleNamespace(request=request, curl_infos=[])
    instrument_transport(SimpleNamespace(_async_curl_session=transport), sink)

    class Scraper:
        async def scrape_book(self, store, url):
            await transport.request("GET", url=url)
            # Simulate a library retry through the actual installed attempt hook.
            with pytest.raises(ScrapingError) as error:
                await transport.request("GET", url=url)
            rejected_retries.append(error.value.reason)
            return SimpleNamespace(price=99, status="activo", checked_at=now[0])

    processor = RelationProcessor(context, Scraper(), clock=lambda: now[0])
    batch = ScrapingBatch(processor.list_page, processor.process, clock=lambda: now[0])
    try:
        summary = await batch.run()
        assert calls and all(stamp == start for _, stamp in calls)
        assert len(events) == len(calls)
        assert rejected_retries == ["schedule_skipped"] * len(calls)
        assert summary.selected == 12
        assert summary.successful == len(calls)
        assert summary.skipped == 12 - len(calls)
        assert summary.failed == summary.omitted == 0
        called = {url for url, _ in calls}
        async with context() as repos:
            for row in rows:
                saved = await repos.relations.get(row.id)
                if row.product_url not in called:
                    assert saved.current_price == 12
                    assert saved.last_checked is None
                    assert saved.scrape_generation in (0, 1)
                    if row.scrape_group == 0:
                        assert saved.next_check_at == start.replace(hour=22)
                    else:
                        assert saved.scrape_generation == 0
                        assert saved.next_check_at == row.next_check_at
            # Histories exist only for requests actually begun in the original slot.
            async with factory() as session:
                history = (await session.execute(select(PriceHistoryModel))).scalars().all()
                assert len(history) == len(calls)
    finally:
        await engine.dispose()
