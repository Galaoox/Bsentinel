from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from bsentinel.domain.models import Book, BookStoreRelation, Store
from bsentinel.infrastructure.persistence.in_memory import InMemoryRelationRepository, InMemoryStore
from bsentinel.infrastructure.persistence.sqlalchemy.models import BookModel, StoreModel
from bsentinel.infrastructure.persistence.sqlalchemy.relations import SQLRelationRepository


@pytest.mark.parametrize("backend", ["memory", "sql"])
async def test_due_filter_keyset_excludes_disabled_and_future(schedule_db, backend):
    now = datetime(2026, 10, 8, 12, tzinfo=UTC)
    factory, (book_id, store_id) = schedule_db
    memory = InMemoryStore()
    store = Store(id=UUID(store_id))
    memory.stores[store.id] = store
    async with factory() as session:
        repo = (
            SQLRelationRepository(session)
            if backend == "sql"
            else InMemoryRelationRepository(memory)
        )
        assert hasattr(repo, "list_due"), "SQL due selection missing"
        for i in range(7):
            book = Book(id=UUID(book_id) if i == 0 else uuid4(), is_deleted=i == 4)
            memory.books[book.id] = book
            if i:
                session.add(
                    BookModel(
                        id=str(book.id), title="fixture", is_deleted=book.is_deleted, created_at=now
                    )
                )
            rel = BookStoreRelation(
                book_id=book.id,
                store_id=store.id,
                scrape_group=i % 3,
                next_check_at=now + timedelta(minutes=1) if i == 5 else now - timedelta(hours=1),
            )
            await repo.add(rel)
        await session.commit()
        first = await repo.list_due(now, limit=2)
        assert len(first) == 2
        cursor = (first[-1].next_check_at, first[-1].id)
        rest = await repo.list_due(now, limit=10, after=cursor)
        assert len(rest) == 3
        assert len({r.id for r in first + rest}) == 5
        assert all(r.next_check_at <= now for r in first + rest)
        if backend == "sql":
            model = await session.get(StoreModel, store_id)
            model.is_active = False
            await session.commit()
        else:
            store.is_active = False
        assert await repo.list_due(now, limit=10) == []
