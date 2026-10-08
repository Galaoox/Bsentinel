from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID

import pytest

from bsentinel.domain.models import BookStoreRelation
from bsentinel.exceptions import ScrapingError
from bsentinel.infrastructure.persistence.scraping_batch import RelationProcessor
from bsentinel.infrastructure.persistence.sqlalchemy import (
    SQLBookRepository,
    SQLHistoryRepository,
    SQLRelationRepository,
    SQLStoreRepository,
)


@pytest.mark.parametrize('group,hour,minute,force,outcome', [
    (0, 18, 0, False, 'skipped'), (1, 22, 0, False, 'skipped'),
    (1, 22, 20, False, 'successful'), (0, 22, 0, False, 'successful'),
    (0, 18, 0, True, 'successful'),
])
async def test_real_processor_admission_and_manual_future_slot(schedule_db, group, hour, minute, force, outcome):
    factory, (book_id, store_id) = schedule_db
    now = datetime(2026, 10, 8, hour, minute, tzinfo=UTC)
    future = datetime(2026, 10, 8, 22, group * 20, tzinfo=UTC)
    row = BookStoreRelation(book_id=UUID(book_id), store_id=UUID(store_id), current_price=12,
                            scrape_group=group, next_check_at=future if force else future - timedelta(hours=9))
    @asynccontextmanager
    async def context():
        async with factory() as session, session.begin():
            yield SimpleNamespace(books=SQLBookRepository(session), stores=SQLStoreRepository(session),
                                  relations=SQLRelationRepository(session), history=SQLHistoryRepository(session))
    async with context() as repos:
        await repos.relations.add(row)
    calls = []
    class Scraper:
        async def scrape_book(self, store, url):
            calls.append(store.id)
            return SimpleNamespace(price=99, status='activo', checked_at=now)
    result = await RelationProcessor(context, Scraper(), clock=lambda: now).process(row, now, force=force)
    assert result == outcome
    assert len(calls) == (outcome == 'successful')
    async with context() as repos:
        loaded = await repos.relations.get(row.id)
        if force:
            assert loaded.next_check_at == future
            assert loaded.scrape_generation > row.scrape_generation
        elif group == 1 and hour == 22 and minute == 0:
            assert loaded.next_check_at == future
        else:
            assert loaded.next_check_at > now


@pytest.mark.parametrize('reason,outcome', [('captcha_blocked', 'captcha'), ('store_paused', 'paused')])
async def test_failed_periodic_preserves_price_history_and_waits_next_window(schedule_db, reason, outcome):
    factory, (book_id, store_id) = schedule_db
    now = datetime(2026, 10, 8, 13, tzinfo=UTC)
    row = BookStoreRelation(book_id=UUID(book_id), store_id=UUID(store_id), scrape_group=0,
                           next_check_at=now, current_price=12, last_checked=now - timedelta(days=1))
    @asynccontextmanager
    async def context():
        async with factory() as session, session.begin():
            yield SimpleNamespace(books=SQLBookRepository(session), stores=SQLStoreRepository(session),
                                  relations=SQLRelationRepository(session), history=SQLHistoryRepository(session))
    async with context() as repos:
        await repos.relations.add(row)
    class Scraper:
        async def scrape_book(self, store, url):
            raise ScrapingError('fixture', reason=reason)
    assert await RelationProcessor(context, Scraper(), clock=lambda: now).process(row, now) == outcome
    async with context() as repos:
        saved = await repos.relations.get(row.id)
        assert saved.current_price == 12
        assert saved.last_checked == row.last_checked
        assert saved.next_check_at == datetime(2026, 10, 8, 22, tzinfo=UTC)
        assert not await repos.history.list(book_id=row.book_id, source='all', state=None, start_date=None, end_date=None)


async def test_publication_failure_cannot_replay_same_window_after_restart(schedule_db):
    factory, (book_id, store_id) = schedule_db
    now = datetime(2026, 10, 8, 13, tzinfo=UTC)
    row = BookStoreRelation(book_id=UUID(book_id), store_id=UUID(store_id), scrape_group=0,
                           next_check_at=now, current_price=12)
    broken = [False]
    @asynccontextmanager
    async def context():
        async with factory() as session, session.begin():
            history = SQLHistoryRepository(session)
            if broken[0]:
                async def fail(record):
                    raise RuntimeError('fixture publication failure')
                history.add = fail
            yield SimpleNamespace(books=SQLBookRepository(session), stores=SQLStoreRepository(session),
                                  relations=SQLRelationRepository(session), history=history)
    async with context() as repos:
        await repos.relations.add(row)
    calls = []
    class Scraper:
        async def scrape_book(self, store, url):
            calls.append(store.id)
            return SimpleNamespace(price=99, status='activo', checked_at=now)
    broken[0] = True
    with pytest.raises(RuntimeError):
        await RelationProcessor(context, Scraper(), clock=lambda: now).process(row, now)
    async with context() as repos:
        saved = await repos.relations.get(row.id)
        assert saved.next_check_at == now.replace(hour=22)
        assert saved.current_price == 12
    broken[0] = False
    assert await RelationProcessor(context, Scraper(), clock=lambda: now).process(saved, now) == 'omitted'
    assert len(calls) == 1


async def test_queued_periodic_request_expiring_window_sends_no_http(schedule_db):
    import asyncio

    from bsentinel.infrastructure.scraping.configured import ConfiguredStoreScraper
    from bsentinel.infrastructure.scraping.limited_runtime import LimitedRuntime
    from bsentinel.infrastructure.scraping.store_guard import MemoryBlockPersistence, StoreGuard
    factory, (book_id, store_id) = schedule_db
    now = [datetime(2026, 10, 8, 13, tzinfo=UTC)]
    row = BookStoreRelation(book_id=UUID(book_id), store_id=UUID(store_id), scrape_group=0,
                           next_check_at=now[0], current_price=12)
    @asynccontextmanager
    async def context():
        async with factory() as session, session.begin():
            yield SimpleNamespace(books=SQLBookRepository(session), stores=SQLStoreRepository(session),
                                  relations=SQLRelationRepository(session), history=SQLHistoryRepository(session))
    async with context() as repos:
        await repos.relations.add(row)
    queued = asyncio.Event()
    class Backend:
        async def fetch(self, url):
            raise AssertionError('Expired window must never send HTTP')
    class Runtime(LimitedRuntime):
        async def fetch(self, url):
            queued.set()
            return await super().fetch(url)
    runtime = Runtime(Backend(), concurrency=1)
    await runtime._permits.acquire()
    scraper = ConfiguredStoreScraper(runtime, store_guard=StoreGuard(MemoryBlockPersistence()))
    task = asyncio.create_task(RelationProcessor(context, scraper, clock=lambda: now[0]).process(row, now[0]))
    await asyncio.wait_for(queued.wait(), 1)
    now[0] += timedelta(seconds=1200)
    runtime._permits.release()
    assert await task == 'skipped'
    async with context() as repos:
        saved = await repos.relations.get(row.id)
        assert saved.current_price == 12
        assert saved.next_check_at == now[0].replace(hour=22, minute=0, second=0)
        assert saved.last_checked is None
