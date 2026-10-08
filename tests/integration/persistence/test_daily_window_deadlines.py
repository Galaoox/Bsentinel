import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from bsentinel.application.services.scraping_batch import ScrapingBatch
from bsentinel.domain.models import BookStoreRelation
from bsentinel.infrastructure.persistence.scraping_batch import RelationProcessor
from bsentinel.infrastructure.persistence.sqlalchemy import (
    SQLBookRepository,
    SQLHistoryRepository,
    SQLRelationRepository,
    SQLStoreRepository,
)
from bsentinel.infrastructure.persistence.sqlalchemy.base import Base
from bsentinel.infrastructure.persistence.sqlalchemy.models import BookModel, StoreModel


@pytest.mark.asyncio
async def test_progressing_clock_checks_entire_cohort_in_both_windows(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/review.db")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    now = [datetime(2026, 10, 8, 13, tzinfo=UTC)]
    async with factory() as session, session.begin():
        session.add_all(
            [
                BookModel(id=str(UUID(int=1000 + i)), title="fixture", created_at=now[0])
                for i in range(60)
            ]
            + [
                StoreModel(
                    id=str(UUID(int=998)),
                    name="fixture",
                    domain="fixture.invalid",
                    country_code="CO",
                    created_at=now[0],
                )
            ]
        )

    @asynccontextmanager
    async def context():
        async with factory() as session, session.begin():
            yield SimpleNamespace(
                books=SQLBookRepository(session),
                stores=SQLStoreRepository(session),
                relations=SQLRelationRepository(session),
                history=SQLHistoryRepository(session),
            )

    rows = [
        BookStoreRelation(
            id=UUID(int=i + 1),
            book_id=UUID(int=1000 + i),
            store_id=UUID(int=998),
            product_url=f"https://fixture.invalid/{i}",
            scrape_group=0,
            next_check_at=now[0],
            current_price=12,
        )
        for i in range(60)
    ]
    async with context() as repos:
        for row in rows:
            await repos.relations.add(row)
    calls = []

    class Scraper:
        async def scrape_book(self, store, url):
            calls.append(url)
            # Virtual aggregate throughput: 3 workers x 30 seconds/request.
            now[0] += timedelta(seconds=10)
            await asyncio.sleep(0)
            return SimpleNamespace(price=99, status="activo", checked_at=now[0])

    processor = RelationProcessor(context, Scraper(), clock=lambda: now[0])
    batch = ScrapingBatch(processor.list_page, processor.process, clock=lambda: now[0])
    results = []
    for hour in (13, 22):
        now[0] = now[0].replace(hour=hour, minute=0, second=0)
        start = len(calls)
        summary = await batch.run()
        results.append((summary.successful, summary.skipped, set(calls[start:])))
    print(
        "STARVATION",
        [(s, k, len(c)) for s, k, c in results],
        "SAME_HEAD",
        results[0][2] == results[1][2],
    )
    async with context() as repos:
        unchanged = [
            row.id for row in rows if (await repos.relations.get(row.id)).last_checked is None
        ]
    print("NEVER_CHECKED", len(unchanged))
    await engine.dispose()
    assert all(success == 60 and skipped == 0 for success, skipped, _ in results)
    assert batch.peak_queue <= 6
    assert len(unchanged) == 0, (
        "Tail relations were skipped in both authorized windows despite available cohort time"
    )


async def test_processor_rechecks_deadline_after_repository_reads(schedule_db):
    factory, (book_id, store_id) = schedule_db
    slot = datetime(2026, 10, 8, 13, tzinfo=UTC)
    now = [slot + timedelta(minutes=19, seconds=59)]
    row = BookStoreRelation(
        book_id=UUID(book_id),
        store_id=UUID(store_id),
        scrape_group=0,
        next_check_at=slot,
        current_price=12,
    )

    @asynccontextmanager
    async def context():
        async with factory() as session, session.begin():
            stores = SQLStoreRepository(session)
            get = stores.get

            async def delayed_get(store_id):
                result = await get(store_id)
                now[0] += timedelta(seconds=2)
                return result

            stores.get = delayed_get
            yield SimpleNamespace(
                books=SQLBookRepository(session),
                stores=stores,
                relations=SQLRelationRepository(session),
                history=SQLHistoryRepository(session),
            )

    async with context() as repos:
        await repos.relations.add(row)
    calls = []

    class Scraper:
        async def scrape_book(self, store, url):
            calls.append(url)
            return SimpleNamespace(price=99, status="activo", checked_at=now[0])

    outcome = await RelationProcessor(context, Scraper(), clock=lambda: now[0]).process(row, now[0])
    assert not calls
    assert outcome == "skipped"
    async with context() as repos:
        saved = await repos.relations.get(row.id)
        assert saved.current_price == 12
        assert saved.last_checked is None
        assert saved.next_check_at == slot.replace(hour=22)
