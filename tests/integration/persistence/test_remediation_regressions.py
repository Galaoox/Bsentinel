"""Regression evidence on disposable SQLite and opt-in PostgreSQL schemas."""

import importlib
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bsentinel.domain.models import Book, BookStoreRelation, PriceHistoryRecord, Store
from bsentinel.exceptions import ScrapingError
from bsentinel.infrastructure.persistence.in_memory import (
    InMemoryBookRepository,
    InMemoryHistoryRepository,
    InMemoryRelationRepository,
    InMemoryStore,
)
from bsentinel.infrastructure.persistence.sqlalchemy import (
    SQLArchiveJobRepository,
    SQLBookRepository,
    SQLHistoryRepository,
    SQLRelationRepository,
    SQLStoreRepository,
)
from bsentinel.infrastructure.persistence.sqlalchemy.models import (
    BookModel,
    PriceHistoryArchiveModel,
    PriceHistoryModel,
)


async def seed(factory, count=3):
    store = Store()
    books = [Book(title=f'Book {i}', authors=['Author']) for i in range(count)]
    relations = [BookStoreRelation(book_id=book.id, store_id=store.id, product_url=f'https://fixture.invalid/{i}')
                 for i, book in enumerate(books)]
    async with factory.begin() as session:
        await SQLStoreRepository(session).add(store)
        for book in books:
            await SQLBookRepository(session).add(book)
        await session.flush()
        for relation in relations:
            await SQLRelationRepository(session).add(relation)
        await session.flush()
    return store, books, relations


@pytest.mark.parametrize('failure', ['scraping', 'database'])
async def test_sql_batch_commits_independently_and_stops_on_database_failure(sql_factory, monkeypatch, failure, caplog):
    factory, _ = sql_factory
    _, books, relations = await seed(factory)
    module = importlib.import_module('bsentinel.infrastructure.api.root_app')
    monkeypatch.setattr(module.settings, 'persistence_backend', 'sql')
    monkeypatch.setattr(module, 'get_session_factory', lambda: factory)
    # Candidate ordering is fixed for deterministic failure position.
    original_list = SQLRelationRepository.list_all
    async def ordered(self):
        rows = await original_list(self)
        return sorted(rows, key=lambda row: row.product_url)
    monkeypatch.setattr(SQLRelationRepository, 'list_all', ordered)
    visited = []
    async def scrape(store, url):
        visited.append(url)
        if url.endswith('/1') and failure == 'scraping':
            raise ScrapingError('unusable page', reason='fetch_failed',
                                diagnostics={'proxy': 'http://private:secret@proxy.invalid'})
        return SimpleNamespace(price=42.0, status='activo', checked_at=datetime.now(UTC))
    monkeypatch.setattr(module, 'scraper_client', SimpleNamespace(scrape_book=scrape))
    original_add = SQLHistoryRepository.add
    async def add(self, record):
        await original_add(self, record)
        if failure == 'database' and record.book_id == books[1].id:
            await original_add(self, record)  # A real primary-key failure at commit.
    monkeypatch.setattr(SQLHistoryRepository, 'add', add)
    if failure == 'database':
        with pytest.raises(IntegrityError):
            await module.run_scraping_batch()
        assert len(visited) == 2
        expected = [relations[0]]
    else:
        assert await module.run_scraping_batch() == 2
        assert len(visited) == 3
        expected = [relations[0], relations[2]]
        logs = ' '.join(str(record.__dict__) for record in caplog.records)
        assert 'fetch_failed' in logs and str(relations[1].id) in logs
        assert 'private' not in logs and 'secret' not in logs
    async with factory() as session:
        histories = (await session.scalars(select(PriceHistoryModel))).all()
        assert {row.relation_id for row in histories} == {str(row.id) for row in expected}
        saved = await SQLRelationRepository(session).list_all()
        assert {row.id for row in saved if row.current_price == 42} == {row.id for row in expected}


@pytest.mark.parametrize('failure', ['scraping', 'unexpected'])
async def test_memory_batch_preserves_confirmed_items(monkeypatch, failure):
    module = importlib.import_module('bsentinel.infrastructure.api.root_app')
    memory = InMemoryStore()
    store = next(iter(memory.stores.values()))
    books = [Book(title=str(i)) for i in range(3)]
    relations = [BookStoreRelation(book_id=book.id, store_id=store.id, product_url=str(i))
                 for i, book in enumerate(books)]
    memory.books = {book.id: book for book in books}
    memory.relations = {row.id: row for row in relations}
    monkeypatch.setattr(module.settings, 'persistence_backend', 'in_memory')
    monkeypatch.setattr(module, 'in_memory_store', memory)
    monkeypatch.setattr(module, 'relation_repository', InMemoryRelationRepository(memory))
    visited = []
    async def scrape(store, url):
        visited.append(url)
        if url == '1':
            raise ScrapingError('fixture') if failure == 'scraping' else RuntimeError('fixture')
        return SimpleNamespace(price=42.0, status='activo', checked_at=datetime.now(UTC))
    monkeypatch.setattr(module, 'scraper_client', SimpleNamespace(scrape_book=scrape))
    if failure == 'unexpected':
        with pytest.raises(RuntimeError):
            await module.run_scraping_batch()
        assert visited == ['0', '1']
        expected = {relations[0].id}
    else:
        assert await module.run_scraping_batch() == 2
        expected = {relations[0].id, relations[2].id}
    assert {row.relation_id for row in memory.history.values()} == expected
    assert {row.id for row in memory.relations.values() if row.current_price == 42} == expected


@pytest.mark.parametrize('condition', ['missing', 'inactive', 'deleted', 'deleted_book'])
async def test_sql_batch_skips_unavailable_store_or_deleted_book(sql_factory, monkeypatch, condition, caplog):
    factory, _ = sql_factory
    _, books, relations = await seed(factory)
    module = importlib.import_module('bsentinel.infrastructure.api.root_app')
    monkeypatch.setattr(module.settings, 'persistence_backend', 'sql')
    monkeypatch.setattr(module, 'get_session_factory', lambda: factory)
    original_list = SQLRelationRepository.list_all
    async def candidates(self):
        rows = sorted(await original_list(self), key=lambda row: row.product_url)
        if condition == 'deleted_book':
            book = await self.session.get(BookModel, str(books[1].id))
            book.is_deleted = True
            await self.session.commit()
        return rows
    monkeypatch.setattr(SQLRelationRepository, 'list_all', candidates)
    original_get = SQLStoreRepository.get
    calls = []
    async def store_get(self, key):
        store = await original_get(self, key)
        calls.append(key)
        if len(calls) == 2 and condition != 'deleted_book':
            if condition == 'missing':
                return None
            if condition == 'inactive':
                store.is_active = False
            else:
                store.is_deleted = True
        return store
    monkeypatch.setattr(SQLStoreRepository, 'get', store_get)
    visited = []
    async def scrape(store, url):
        visited.append(url)
        return SimpleNamespace(price=7.0, status='activo', checked_at=datetime.now(UTC))
    monkeypatch.setattr(module, 'scraper_client', SimpleNamespace(scrape_book=scrape))
    assert await module.run_scraping_batch() == 2
    assert visited == [relations[0].product_url, relations[2].product_url]
    async with factory() as session:
        saved = (await session.scalars(select(PriceHistoryModel))).all()
        assert {row.book_id for row in saved} == {str(books[0].id), str(books[2].id)}
    if condition != 'deleted_book':
        expected = 'not found' if condition == 'missing' else condition
        assert any(expected in getattr(record, 'error_message', '') for record in caplog.records)


@pytest.mark.parametrize('fails', [False, True])
async def test_sql_archive_moves_ids_keeps_latest_and_rolls_back(sql_factory, monkeypatch, fails):
    factory, _ = sql_factory
    store, books, relations = await seed(factory, 2)
    now = datetime.now(UTC)
    records = [PriceHistoryRecord(book_id=book.id, relation_id=relation.id, store_id=store.id,
                                  checked_at=now - timedelta(days=age))
               for book, relation in zip(books, relations) for age in [1, 40, 50, 60]]
    async with factory.begin() as session:
        for record in records:
            await SQLHistoryRepository(session).add(record)
        job = await SQLArchiveJobRepository(session).create()
    if fails:
        original = AsyncSession.execute
        moves_observed = []
        async def fail_after_move(self, statement, *args, **kwargs):
            result = await original(self, statement, *args, **kwargs)
            if getattr(statement, 'is_delete', False):
                await self.flush()
                assert await self.scalar(select(func.count()).select_from(PriceHistoryModel)) == 4
                assert await self.scalar(select(func.count()).select_from(PriceHistoryArchiveModel)) == 4
                moves_observed.append(True)
                raise RuntimeError('archive failure after physical move')
            return result
        monkeypatch.setattr(AsyncSession, 'execute', fail_after_move)
        with pytest.raises(RuntimeError):
            async with factory.begin() as session:
                await SQLArchiveJobRepository(session).run(job.id, 30, 2)
        assert moves_observed == [True]
        expected_active = {str(record.id) for record in records}
        expected_archive = set()
    else:
        async with factory.begin() as session:
            result = await SQLArchiveJobRepository(session).run(job.id, 30, 2)
            assert result.status == 'completed' and result.moved_records == 4
        expected_archive = {str(record.id) for record in records if record.checked_at < now - timedelta(days=45)}
        expected_active = {str(record.id) for record in records} - expected_archive
    async with factory() as session:
        assert set(await session.scalars(select(PriceHistoryModel.id))) == expected_active
        assert set(await session.scalars(select(PriceHistoryArchiveModel.id))) == expected_archive


async def test_sql_memory_pagination_parity_bounded_queries(sql_factory):
    factory, engine = sql_factory
    store, books, relations = await seed(factory, 4)
    memory = InMemoryStore()
    moment = datetime(2025, 1, 1, tzinfo=UTC)
    for i, book in enumerate(books):
        book.title = 'Percent%_ literal' if i < 3 else 'ÁRBOL'
        book.authors = ['Match_author', 'match_author duplicate', 'ÁRBOL']
        book.categories = ['Match%category', 'match%category duplicate']
        book.created_at = moment
        book.is_deleted = i == 2
        memory.books[book.id] = book
    histories = [PriceHistoryRecord(book_id=books[0].id, relation_id=relations[0].id, store_id=store.id,
                                    checked_at=moment, state='activo', archived=i % 2 == 1)
                 for i in range(5)]
    memory.history = {row.id: row for row in histories}
    async with factory.begin() as session:
        for book in books:
            await SQLBookRepository(session).add(book)
            model = await session.get(BookModel, str(book.id))
            model.created_at = moment
        for row in histories:
            model = PriceHistoryArchiveModel if row.archived else PriceHistoryModel
            session.add(model(id=str(row.id), book_id=str(row.book_id), relation_id=str(row.relation_id),
                              store_id=str(row.store_id), price=42, state=row.state,
                              checked_at=row.checked_at, archived=row.archived))
    statements = []
    def capture(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)
    event.listen(engine.sync_engine, 'before_cursor_execute', capture)
    try:
        async with factory() as session:
            for filter_key in ['q', 'author']:
                filters = dict(include_deleted=False, q=None, isbn=None, author=None,
                               category=None, page=1, limit=2)
                filters[filter_key] = 'árbol'
                expected, count = await InMemoryBookRepository(memory).list_page(**filters)
                actual, total = await SQLBookRepository(session).list_page(**filters)
                assert total == count
                assert [row.id for row in actual] == [row.id for row in expected]
            for page in [1, 2, 8]:
                filters = dict(include_deleted=False, q='%_', isbn=None, author='_AUTHOR',
                               category='%CATEGORY', page=page, limit=1)
                expected, count = await InMemoryBookRepository(memory).list_page(**filters)
                actual, total = await SQLBookRepository(session).list_page(**filters)
                assert total == count == 2
                assert [row.id for row in actual] == [row.id for row in expected]
            for source, count in [('active', 3), ('archive', 2), ('all', 5)]:
                for page in [1, 2, 9]:
                    filters = dict(book_id=books[0].id, source=source, state='activo',
                                   start_date=moment, end_date=moment, page=page, limit=2)
                    expected, _ = await InMemoryHistoryRepository(memory).list_page(**filters)
                    actual, total = await SQLHistoryRepository(session).list_page(**filters)
                    assert total == count
                    assert [row.id for row in actual] == [row.id for row in expected]
    finally:
        event.remove(engine.sync_engine, 'before_cursor_execute', capture)
    data_queries = [query for query in statements if ('FROM books' in query or 'FROM price_history' in query)
                    and 'count(' not in query.lower()]
    assert data_queries and all('LIMIT' in query.upper() for query in data_queries)
    assert any('EXISTS' in query.upper() for query in statements)
    assert any('UNION ALL' in query.upper() for query in statements)
