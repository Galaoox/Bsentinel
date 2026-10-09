import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID

import pytest
from sqlalchemy import func, select

from bsentinel.domain.models import BookStoreRelation
from bsentinel.exceptions import ScrapingError
from bsentinel.infrastructure.persistence.sqlalchemy import (
    SQLBookRepository,
    SQLHistoryRepository,
    SQLRelationRepository,
    SQLStoreRepository,
)
from bsentinel.infrastructure.persistence.sqlalchemy.models import (
    BookModel,
    BookStoreRelationModel,
    PriceHistoryModel,
    StoreModel,
)


async def test_wired_manual_never_checked_relation_shares_periodic_guard(monkeypatch):
    from importlib import import_module

    from bsentinel.domain.models import Book
    from bsentinel.infrastructure.persistence.in_memory import InMemoryStore

    app = import_module("bsentinel.infrastructure.api.root_app")
    memory = InMemoryStore()
    book = Book()
    memory.books[book.id] = book
    store = next(iter(memory.stores.values()))
    now = datetime(2026, 10, 8, 13, tzinfo=UTC)
    original_processor = app.RelationProcessor
    monkeypatch.setattr(app, "RelationProcessor", lambda *args: original_processor(*args, clock=lambda: now))
    row = BookStoreRelation(book_id=book.id, store_id=store.id, scrape_group=0,
                            next_check_at=now, last_checked=None)
    memory.relations[row.id] = row
    entered, release = asyncio.Event(), asyncio.Event()
    calls = 0

    class Scraper:
        async def scrape_book(self, store, url):
            nonlocal calls
            calls += 1
            entered.set()
            await release.wait()
            return SimpleNamespace(price=99, status="activo", checked_at=now)

    monkeypatch.setattr(app.settings, "persistence_backend", "in_memory")
    monkeypatch.setattr(app, "in_memory_store", memory)
    monkeypatch.setattr(app, "scraper_client", Scraper())
    # Use the actual request service wiring (including its refresh callback).
    service = app._build_sql_services(None)["scraping"]
    from bsentinel.infrastructure.persistence.in_memory import (
        InMemoryHistoryRepository,
        InMemoryRelationRepository,
        InMemoryStoreRepository,
    )
    service.stores = InMemoryStoreRepository(memory)
    service.relations = InMemoryRelationRepository(memory)
    service.history = InMemoryHistoryRepository(memory)
    manual_input = await service.relations.get(row.id)
    periodic = asyncio.create_task(app._process_due_relation(row, now))
    await asyncio.wait_for(entered.wait(), 1)
    manual = asyncio.create_task(service.scrape_relation(manual_input))
    try:
        await asyncio.sleep(0.02)
        release.set()
        assert await periodic == "successful"
        await manual
    finally:
        release.set()
        await asyncio.gather(periodic, manual, return_exceptions=True)
    assert calls == 1
    assert len(memory.history) == 1
    assert memory.relations[row.id].current_price == 99
    assert manual_input.last_checked == now

@pytest.mark.parametrize("backend", ["memory", "sql"])
@pytest.mark.parametrize("change", ["reactivate", "restore", "url_aba"])
async def test_force_future_same_slot_invalidates_inflight_result(schedule_db, monkeypatch, backend, change):
    from dataclasses import replace

    from bsentinel.application.services.catalog import CatalogCommandService
    from bsentinel.domain.models import Book, Store
    from bsentinel.infrastructure.persistence import scraping_batch
    from bsentinel.infrastructure.persistence.in_memory import (
        InMemoryBookRepository,
        InMemoryHistoryRepository,
        InMemoryRelationRepository,
        InMemoryStore,
        InMemoryStoreRepository,
    )
    from bsentinel.infrastructure.persistence.in_memory.transactions import (
        InMemoryCatalogTransaction,
    )

    now = datetime(2026, 10, 8, 12, 10, tzinfo=UTC)
    for module in ["in_memory.relations", "in_memory.stores", "sqlalchemy.relations", "sqlalchemy.stores"]:
        monkeypatch.setattr("bsentinel.infrastructure.persistence." + module + ".now_utc", lambda: now)
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return now

    monkeypatch.setattr("bsentinel.application.services.catalog.datetime", FixedDatetime)
    factory, (book_id, store_id) = schedule_db
    memory = InMemoryStore()
    memory.books[UUID(book_id)] = Book(id=UUID(book_id))
    memory.stores[UUID(store_id)] = Store(id=UUID(store_id))

    @asynccontextmanager
    async def context():
        if backend == "sql":
            async with factory() as session, session.begin():
                yield SimpleNamespace(books=SQLBookRepository(session), stores=SQLStoreRepository(session),
                                      relations=SQLRelationRepository(session), history=SQLHistoryRepository(session))
        else:
            async with InMemoryCatalogTransaction(memory) as tx:
                yield SimpleNamespace(books=InMemoryBookRepository(tx.working), stores=InMemoryStoreRepository(tx.working),
                                      relations=InMemoryRelationRepository(tx.working), history=InMemoryHistoryRepository(tx.working))

    row = BookStoreRelation(book_id=UUID(book_id), store_id=UUID(store_id),
                            product_url="https://fixture.invalid/original", current_price=12,
                            last_checked=now - timedelta(hours=1), scrape_group=0,
                            next_check_at=now.replace(hour=13, minute=0))
    async with context() as repos:
        await repos.relations.add(row)

    class Scraper:
        async def scrape_book(self, store, url):
            if change == "reactivate" and backend == "memory":
                stores = InMemoryStoreRepository(memory)
                await stores.save(replace(store, is_active=False))
                await stores.save(replace(store, is_active=True))
            elif change == "reactivate":
                async with context() as repos:
                    await repos.stores.save(replace(store, is_active=False))
                async with context() as repos:
                    await repos.stores.save(replace(store, is_active=True))
            elif change == "restore":
                async with context() as repos:
                    await repos.books.add(replace(await repos.books.get(row.book_id), is_deleted=True))
                async with context() as repos:
                    await CatalogCommandService(books=repos.books, stores=repos.stores,
                                                relations=repos.relations, metadata=None, scraper=None).restore_book(row.book_id)
            else:
                for url in ["https://fixture.invalid/edited", row.product_url]:
                    async with context() as repos:
                        current = await repos.relations.get(row.id)
                        await repos.relations.save(replace(current, product_url=url))
            async with context() as repos:
                assert (await repos.relations.get(row.id)).next_check_at == row.next_check_at
            return SimpleNamespace(price=99, status="activo", checked_at=now)

    processor = scraping_batch.RelationProcessor(context, Scraper(), clock=lambda: now)
    assert await processor.process(row, now, force=True) == "omitted"
    async with context() as repos:
        loaded = await repos.relations.get(row.id)
        assert loaded.current_price == 12
        assert loaded.last_checked == row.last_checked
        assert loaded.next_check_at == row.next_check_at
        assert loaded.scrape_generation > row.scrape_generation
        assert not await repos.history.list(book_id=row.book_id, source="all", state=None, start_date=None, end_date=None)


async def test_postgres_publication_parent_locks_allow_bulk_foreign_keys(schedule_db):
    from uuid import uuid4

    factory, (book_id, store_id) = schedule_db
    if factory.kw["bind"].dialect.name != "postgresql":
        pytest.skip("PostgreSQL row locks required")
    row = BookStoreRelation(book_id=UUID(book_id), store_id=UUID(store_id))
    async with factory() as session, session.begin():
        await SQLRelationRepository(session).add(row)

    async with factory() as publisher, publisher.begin():
        assert await SQLRelationRepository(publisher).get_for_update(row.id)

        async def bulk_insert():
            async with factory() as session, session.begin():
                new_id = uuid4()
                session.add(BookModel(id=str(new_id), title="bulk fixture", created_at=datetime.now(UTC)))
                await SQLRelationRepository(session).add(BookStoreRelation(book_id=new_id, store_id=UUID(store_id)))

        # Parent locks must serialize state changes, not block FK KEY SHARE locks.
        await asyncio.wait_for(bulk_insert(), 2)


@pytest.mark.parametrize("first", ["publication", "reactivation"])
async def test_postgres_reactivation_and_publication_serialize_without_deadlock(schedule_db, first):
    from dataclasses import replace

    from bsentinel.domain.models import Store

    factory, (book_id, store_id) = schedule_db
    if factory.kw["bind"].dialect.name != "postgresql":
        pytest.skip("PostgreSQL row locks required")
    store = Store(id=UUID(store_id), is_active=False)
    row = BookStoreRelation(book_id=UUID(book_id), store_id=UUID(store_id))
    async with factory() as session, session.begin():
        await SQLStoreRepository(session).save(store)
        await SQLRelationRepository(session).add(row)

    async def operation(session, kind):
        if kind == "publication":
            return await SQLRelationRepository(session).get_for_update(row.id)
        await SQLStoreRepository(session).save(replace(store, is_active=True))

    started, finished = asyncio.Event(), asyncio.Event()

    async def second():
        async with factory() as session, session.begin():
            started.set()
            await operation(session, "reactivation" if first == "publication" else "publication")
            finished.set()

    async with factory() as session:
        async with session.begin():
            await operation(session, first)
            task = asyncio.create_task(second())
            await started.wait()
            await asyncio.sleep(0.05)
            assert not finished.is_set()
        await asyncio.wait_for(task, 2)
    async with factory() as session:
        assert (await SQLRelationRepository(session).get(row.id)).scrape_generation == 1
        assert (await SQLStoreRepository(session).get(UUID(store_id))).is_active


async def test_mutating_manual_input_during_fetch_cannot_validate_stale_result():
    from bsentinel.domain.models import Book
    from bsentinel.infrastructure.persistence.in_memory import (
        InMemoryBookRepository,
        InMemoryHistoryRepository,
        InMemoryRelationRepository,
        InMemoryStore,
        InMemoryStoreRepository,
    )
    from bsentinel.infrastructure.persistence.scraping_batch import RelationProcessor

    memory = InMemoryStore()
    book = Book()
    memory.books[book.id] = book
    store = next(iter(memory.stores.values()))
    now = datetime.now(UTC)
    row = BookStoreRelation(
        book_id=book.id,
        store_id=store.id,
        scrape_group=0,
        next_check_at=now,
        product_url="https://fixture.invalid/old",
    )
    memory.relations[row.id] = row

    @asynccontextmanager
    async def context():
        yield SimpleNamespace(
            books=InMemoryBookRepository(memory),
            stores=InMemoryStoreRepository(memory),
            relations=InMemoryRelationRepository(memory),
            history=InMemoryHistoryRepository(memory),
        )

    class Scraper:
        async def scrape_book(self, store, url):
            row.product_url = "https://fixture.invalid/new"
            return SimpleNamespace(price=99, status="activo", checked_at=now)

    processor = RelationProcessor(context, Scraper(), clock=lambda: now)
    assert await processor.process(row, now, force=True) == "omitted"
    assert not memory.history
    assert memory.relations[row.id].current_price is None


async def test_manual_refresh_and_periodic_result_share_relation_guard(schedule_db):
    from bsentinel.infrastructure.persistence.scraping_batch import RelationProcessor

    factory, (book_id, store_id) = schedule_db
    now = datetime.now(UTC)
    row = BookStoreRelation(
        book_id=UUID(book_id),
        store_id=UUID(store_id),
        scrape_group=0,
        next_check_at=now + timedelta(minutes=10),
        last_checked=now - timedelta(hours=1),
    )
    async with factory() as session:
        await SQLRelationRepository(session).add(row)
        await session.commit()

    @asynccontextmanager
    async def context():
        async with factory() as session, session.begin():
            yield SimpleNamespace(
                books=SQLBookRepository(session),
                stores=SQLStoreRepository(session),
                relations=SQLRelationRepository(session),
                history=SQLHistoryRepository(session),
            )

    calls = 0

    class Scraper:
        async def scrape_book(self, store, url):
            nonlocal calls
            calls += 1
            await asyncio.sleep(0.01)
            return SimpleNamespace(price=99, status="activo", checked_at=now)

    processor = RelationProcessor(context, Scraper(), clock=lambda: now)
    outcomes = await asyncio.gather(
        processor.process(row, now, force=True), processor.process(row, now, force=True)
    )
    assert sorted(outcomes) == ["omitted", "successful"]
    assert calls == 1
    assert not processor.locks._entries
    async with factory() as session:
        assert await session.scalar(select(func.count()).select_from(PriceHistoryModel)) == 1


@pytest.mark.parametrize(
    "failure", ["none", "fetch", "sql", "deleted", "inactive", "url", "rescheduled", "cancel"]
)
async def test_result_is_atomic_and_revalidates_without_session_during_fetch(
    schedule_db, failure, caplog
):
    import logging

    caplog.set_level(logging.INFO)
    from bsentinel.infrastructure.persistence.scraping_batch import RelationProcessor

    factory, (book_id, store_id) = schedule_db
    now = datetime(2026, 10, 8, 13, tzinfo=UTC)
    row = BookStoreRelation(
        book_id=UUID(book_id),
        store_id=UUID(store_id),
        product_url="https://fixture.invalid/book",
        current_price=12,
        status="activo",
        last_checked=now - timedelta(hours=2),
        scrape_group=0,
        next_check_at=now,
    )
    async with factory() as session:
        await SQLRelationRepository(session).add(row)
        await session.commit()
    opened = 0

    @asynccontextmanager
    async def context():
        nonlocal opened
        async with factory() as session, session.begin():
            opened += 1
            try:
                history = SQLHistoryRepository(session)
                if failure == "sql":

                    async def broken(record):
                        await history_original(record)
                        raise RuntimeError("write fixture")

                    history_original = history.add
                    history.add = broken
                yield SimpleNamespace(
                    books=SQLBookRepository(session),
                    stores=SQLStoreRepository(session),
                    relations=SQLRelationRepository(session),
                    history=history,
                )
            finally:
                opened -= 1

    class Scraper:
        async def scrape_book(self, store, url):
            assert opened == 0, "SQL session leaked into HTTP"
            if failure == "fetch":
                raise ScrapingError("fetch fixture")
            if failure == "cancel":
                raise asyncio.CancelledError()
            async with factory() as session:
                if failure == "deleted":
                    (await session.get(BookModel, book_id)).is_deleted = True
                if failure == "inactive":
                    (await session.get(StoreModel, store_id)).is_active = False
                model = await session.get(BookStoreRelationModel, str(row.id))
                if failure == "url":
                    model.product_url = "https://fixture.invalid/changed"
                if failure == "rescheduled":
                    model.next_check_at = now + timedelta(hours=5)
                await session.commit()
            return SimpleNamespace(price=99, status="activo", checked_at=now + timedelta(minutes=1))

    processor = RelationProcessor(context, Scraper(), clock=lambda: now + timedelta(minutes=1))
    if failure in {"sql", "cancel"}:
        with pytest.raises(RuntimeError if failure == "sql" else asyncio.CancelledError):
            await processor.process(row, now)
    else:
        outcome = await processor.process(row, now)
        assert outcome == (
            "successful" if failure == "none" else "failed" if failure == "fetch" else "omitted"
        )
        if outcome == "omitted":
            records = [r for r in caplog.records if r.message == "Scraping relation omitted"]
            assert len(records) == 1
            assert records[0].relation_id == str(row.id)
            assert records[0].omission_reason in {"disabled", "url_changed", "rescheduled"}
    async with factory() as session:
        loaded = (await SQLRelationRepository(session).list_all())[0]
        history_count = await session.scalar(select(func.count()).select_from(PriceHistoryModel))
        assert history_count == (1 if failure == "none" else 0)
        assert loaded.current_price == (99 if failure == "none" else 12)
        assert loaded.last_checked == (
            now + timedelta(minutes=1) if failure == "none" else row.last_checked
        )
        # Admission reserves the next window even if publication fails/cancels.
        expected = now + timedelta(hours=5 if failure == "rescheduled" else 9)
        assert loaded.next_check_at == expected
