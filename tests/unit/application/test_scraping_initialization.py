from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from bsentinel.application.services.pricing import ScrapingService
from bsentinel.domain.models import Book, BookStoreRelation
from bsentinel.infrastructure.persistence.in_memory import (
    InMemoryBookRepository,
    InMemoryHistoryRepository,
    InMemoryRelationRepository,
    InMemoryStore,
    InMemoryStoreRepository,
)
from bsentinel.infrastructure.persistence.sqlalchemy.relations import SQLRelationRepository


@pytest.mark.parametrize("backend", ["memory", "sql"])
async def test_new_relation_initializes_schedule_idempotently(schedule_db, backend):
    factory, (book_id, store_id) = schedule_db
    memory = InMemoryStore()
    now = datetime.now(UTC)
    async with factory() as session:
        repo = (
            SQLRelationRepository(session)
            if backend == "sql"
            else InMemoryRelationRepository(memory)
        )
        relation = BookStoreRelation(
            book_id=UUID(book_id), store_id=UUID(store_id), last_checked=now
        )
        await repo.add(relation)
        assert relation.scrape_group == 0
        assert relation.next_check_at >= now + timedelta(hours=1)
        original = relation.next_check_at
        await repo.save(relation)
        await session.commit()
        assert relation.next_check_at == original


async def test_group_assignment_is_balanced_across_concurrent_transactions(schedule_db):
    import asyncio
    from collections import Counter
    from uuid import uuid4

    from bsentinel.infrastructure.persistence.sqlalchemy.models import BookModel

    factory, (_, store_id) = schedule_db
    now = datetime.now(UTC)
    book_ids = [uuid4() for _ in range(9)]
    async with factory() as session:
        session.add_all(
            [
                BookModel(id=str(book_id), title="concurrent fixture", created_at=now)
                for book_id in book_ids
            ]
        )
        await session.commit()

    async def create(book_id):
        async with factory() as session:
            row = BookStoreRelation(book_id=book_id, store_id=UUID(store_id))
            await SQLRelationRepository(session).add(row)
            await asyncio.sleep(0.001)
            await session.commit()
            return row.scrape_group

    groups = await asyncio.gather(*(create(book_id) for book_id in book_ids))
    assert Counter(groups) == {0: 3, 1: 3, 2: 3}


async def test_mutable_in_memory_url_edit_reinitializes_calendar():
    memory = InMemoryStore()
    repo = InMemoryRelationRepository(memory)
    row = BookStoreRelation(
        scrape_group=0,
        next_check_at=datetime(2020, 1, 1, tzinfo=UTC),
        product_url="https://fixture.invalid/old",
    )
    await repo.add(row)
    editing = await repo.get(row.id)
    editing.product_url = "https://fixture.invalid/new"
    await repo.save(editing)
    assert (await repo.get(row.id)).next_check_at > datetime.now(UTC)


async def test_existing_manual_refresh_delegates_to_independent_transaction():
    from unittest.mock import AsyncMock

    now = datetime.now(UTC)
    relation = BookStoreRelation(last_checked=now)
    callback = AsyncMock()
    service = ScrapingService(
        books=None,
        stores=None,
        relations=None,
        history=None,
        scraper=None,
        refresh_relation=callback,
    )
    await service.scrape_relation(relation)
    callback.assert_awaited_once_with(relation)


async def test_initial_scrape_sets_hourly_calendar_from_checked_timestamp():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    memory = InMemoryStore()
    store = next(iter(memory.stores.values()))
    books = InMemoryBookRepository(memory)
    relations = InMemoryRelationRepository(memory)
    book = Book()
    await books.add(book)
    relation = BookStoreRelation(book_id=book.id, store_id=store.id)
    await relations.add(relation)
    now = datetime.now(UTC)

    class Scraper:
        async def scrape_book(self, store, url):
            return SimpleNamespace(price=42, status="activo", checked_at=now)

    callback = AsyncMock()
    service = ScrapingService(
        books=books,
        stores=InMemoryStoreRepository(memory),
        relations=relations,
        history=InMemoryHistoryRepository(memory),
        scraper=Scraper(),
        refresh_relation=callback,
    )
    await service.scrape_relation(relation, initial=True)
    callback.assert_not_awaited()
    assert relation.next_check_at >= now + timedelta(hours=1)


@pytest.mark.parametrize("backend", ["memory", "sql"])
async def test_store_reactivation_and_url_change_move_schedule_forward(schedule_db, backend):
    from dataclasses import replace

    from bsentinel.infrastructure.persistence.sqlalchemy import SQLStoreRepository

    factory, (book_id, store_id) = schedule_db
    memory = InMemoryStore()
    from bsentinel.domain.models import Store

    store = Store(id=UUID(store_id), is_active=False)
    memory.stores[store.id] = store
    async with factory() as session:
        stores = (
            SQLStoreRepository(session) if backend == "sql" else InMemoryStoreRepository(memory)
        )
        relations = (
            SQLRelationRepository(session)
            if backend == "sql"
            else InMemoryRelationRepository(memory)
        )
        if backend == "sql":
            await stores.save(store)
        relation = BookStoreRelation(
            book_id=UUID(book_id),
            store_id=store.id,
            scrape_group=1,
            next_check_at=datetime(2020, 1, 1, tzinfo=UTC),
            product_url="https://fixture.invalid/old",
        )
        await relations.add(relation)
        await session.commit()
        await stores.save(replace(store, is_active=True))
        await session.commit()
        loaded = await relations.get(relation.id)
        assert loaded.next_check_at > datetime.now(UTC)
        loaded.next_check_at = datetime(2020, 1, 1, tzinfo=UTC)
        await relations.save(loaded)
        await session.commit()
        await relations.save(replace(loaded, product_url="https://fixture.invalid/new"))
        await session.commit()
        changed = await relations.get(relation.id)
        assert changed.scrape_group == 1
        assert changed.next_check_at > datetime.now(UTC)


async def test_restoring_book_moves_overdue_calendar_to_future():
    from bsentinel.application.services.catalog import CatalogCommandService

    memory = InMemoryStore()
    books = InMemoryBookRepository(memory)
    relations = InMemoryRelationRepository(memory)
    book = Book(is_deleted=True)
    await books.add(book)
    store = next(iter(memory.stores.values()))
    relation = BookStoreRelation(
        book_id=book.id,
        store_id=store.id,
        scrape_group=2,
        next_check_at=datetime(2020, 1, 1, tzinfo=UTC),
    )
    await relations.add(relation)
    service = CatalogCommandService(
        books=books,
        stores=InMemoryStoreRepository(memory),
        relations=relations,
        metadata=None,
        scraper=None,
    )
    await service.restore_book(book.id)
    assert relation.scrape_group == 2
    assert relation.next_check_at > datetime.now(UTC)
