"""End-to-end isolated load, runtime overlap and independent DB results."""

import asyncio
import importlib
from collections import Counter
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

from sqlalchemy import func, select

from bsentinel.domain.models import BookStoreRelation
from bsentinel.infrastructure.persistence.sqlalchemy import (
    SQLHistoryRepository,
    SQLRelationRepository,
)
from bsentinel.infrastructure.persistence.sqlalchemy.models import BookModel, PriceHistoryModel
from bsentinel.infrastructure.scraping.limited_runtime import LimitedRuntime


async def test_hundreds_due_rows_share_runtime_with_import_and_commit_independently(
    schedule_db, monkeypatch
):
    root = importlib.import_module("bsentinel.infrastructure.api.root_app")
    factory, (_, store_id) = schedule_db
    now = datetime(2026, 10, 8, 13, tzinfo=UTC)
    base = now
    original_processor = root.RelationProcessor
    monkeypatch.setattr(root, "RelationProcessor", lambda *args: original_processor(*args, clock=lambda: now))
    rows = []
    async with factory() as session:
        for index in range(303):
            book_id = uuid4()
            session.add(BookModel(id=str(book_id), title=str(index), created_at=now))
            row = BookStoreRelation(
                book_id=book_id,
                store_id=UUID(store_id),
                product_url=f"https://fixture.invalid/{index}",
                scrape_group=index % 3,
                next_check_at=now - timedelta(hours=1),
                last_checked=now - timedelta(hours=2),
                current_price=42,
            )
            await SQLRelationRepository(session).add(row)
            rows.append(row)
        await session.commit()
    own_sessions = Counter()

    async def scope():
        task = asyncio.current_task()
        async with factory() as session:
            own_sessions[task] += 1
            try:
                yield session
                await session.commit()
            except BaseException:
                await session.rollback()
                raise
            finally:
                own_sessions[task] -= 1

    active = peak = 0
    visited = []

    class Backend:
        async def fetch(self, url):
            nonlocal active, peak
            index = int(url.rsplit("/", 1)[-1])
            assert own_sessions[asyncio.current_task()] == 0
            active += 1
            peak = max(peak, active)
            try:
                await asyncio.sleep(0.002)
                if index >= 0:
                    visited.append(index)
                if index >= 0 and index % 11 == 0:
                    raise RuntimeError("isolated fetch failure")
                return SimpleNamespace(
                    price=float(index), status="activo", checked_at=now
                )
            finally:
                active -= 1

    runtime = LimitedRuntime(Backend(), 3)

    class Scraper:
        async def scrape_book(self, store, url):
            return await runtime.fetch(url)

    history_add = SQLHistoryRepository.add

    async def fail_some_writes(repo, record):
        await history_add(repo, record)
        if int(record.price) % 17 == 0:
            raise RuntimeError("isolated database publication failure")

    monkeypatch.setattr(SQLHistoryRepository, "add", fail_some_writes)
    monkeypatch.setattr(root.settings, "persistence_backend", "sql")
    monkeypatch.setattr(root, "session_scope", scope)
    monkeypatch.setattr(root, "scraper_client", Scraper())
    monkeypatch.setattr(root, "scraping_runtime", runtime)
    monkeypatch.setattr(root.scraping_batch, "clock", lambda: now)
    # Import/manual store consultations overlap the periodic workers at the same runtime.
    import_tasks = [
        asyncio.create_task(runtime.fetch(f"https://fixture.invalid/{-i - 1}")) for i in range(12)
    ]
    updated = 0
    for group in range(3):
        now = base + timedelta(minutes=group * 20)
        updated += await root.run_scraping_batch()
    await asyncio.gather(*import_tasks)
    successes = sum(i % 11 != 0 and i % 17 != 0 for i in range(303))
    assert updated == successes
    assert sorted(visited) == list(range(303))
    assert peak == runtime.peak_active == 3
    assert runtime.active == 0
    assert root.scraping_batch.peak_queue <= 6
    assert not any(own_sessions.values())
    async with factory() as session:
        assert (
            await session.scalar(select(func.count()).select_from(PriceHistoryModel)) == successes
        )
        loaded = await SQLRelationRepository(session).list_all()
        assert Counter(row.scrape_group for row in loaded) == {0: 101, 1: 101, 2: 101}
        for row in loaded:
            index = int(row.product_url.rsplit("/", 1)[-1])
            if index % 11 == 0:
                assert row.current_price == 42 and row.last_checked == base - timedelta(hours=2)
                assert row.next_check_at > now
            elif index % 17 == 0:
                assert row.current_price == 42 and row.next_check_at > now
            else:
                assert row.current_price == index and row.next_check_at > now
