"""Real SQL adapters against SQLite and opt-in, isolated PostgreSQL schemas."""
import os
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from bsentinel.domain.models import Book, BookStoreRelation, Store
from bsentinel.infrastructure.persistence.sqlalchemy import (
    SQLBookRepository,
    SQLRelationRepository,
    SQLStoreRepository,
)
from bsentinel.infrastructure.persistence.sqlalchemy.base import Base
from bsentinel.infrastructure.persistence.sqlalchemy.models import BookModel, BookStoreRelationModel
from bsentinel.infrastructure.persistence.sqlalchemy.transactions import SQLCatalogTransaction


async def exercise_transactions(engine):
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, autoflush=False, expire_on_commit=False)
    store = Store()
    async with factory() as session:
        await SQLStoreRepository(session).add(store)
        await session.commit()
    book = Book(title='Isolated', authors=['Author'], isbn='9780134494166')
    async with factory() as session:
        # Auth/query can already have activated autobegin.
        await session.execute(select(BookModel))
        async with SQLCatalogTransaction(session) as tx:
            await SQLBookRepository(session).add(book)
            await tx.flush()
            assert (await SQLBookRepository(session).get_by_isbn(book.isbn)).id == book.id
            await SQLRelationRepository(session).add(BookStoreRelation(book_id=book.id, store_id=store.id, product_url='https://fixture.example/book'))
            await tx.flush()
    async with factory() as session:
        assert await session.scalar(select(func.count()).select_from(BookModel)) == 1
    failed = Book(title='Rollback', authors=[], isbn='9780134494167')
    async with factory() as session:
        with pytest.raises(IntegrityError):
            async with SQLCatalogTransaction(session) as tx:
                await SQLBookRepository(session).add(failed)
                await tx.flush()
                # Database uniqueness failure after a visible first write.
                for _ in range(2):
                    await SQLRelationRepository(session).add(BookStoreRelation(book_id=failed.id, store_id=store.id, product_url='https://fixture.example/duplicate'))
                await tx.flush()
    async with factory() as session:
        assert await session.scalar(select(func.count()).select_from(BookModel)) == 1
        assert await session.scalar(select(func.count()).select_from(BookStoreRelationModel)) == 1


async def test_sqlite_bulk_transaction_visibility_commit_and_rollback(tmp_path):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "bulk.db"}')
    try:
        await exercise_transactions(engine)
    finally:
        await engine.dispose()


@pytest.mark.postgres_smoke
async def test_postgres_bulk_transaction_visibility_commit_and_constraints():
    url = os.environ.get('BULK_TEST_POSTGRES_URL')
    if not url:
        pytest.skip('BULK_TEST_POSTGRES_URL absent; isolated PostgreSQL required')
    parsed = make_url(url)
    assert parsed.host in {'127.0.0.1', 'localhost'}
    assert parsed.database == 'bulk_test', 'Only the disposable bulk_test database is allowed'
    schema = 'bulk_' + uuid4().hex
    admin = create_async_engine(url)
    engine = create_async_engine(url, connect_args={'server_settings': {'search_path': schema}})
    try:
        async with admin.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA {schema}'))
        await exercise_transactions(engine)
    finally:
        await engine.dispose()
        async with admin.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS {schema} CASCADE'))
        await admin.dispose()
