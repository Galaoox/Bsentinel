from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta


async def test_sql_block_survives_restart_and_atomic_max_and_stale_clear(schedule_db):
    from bsentinel.infrastructure.persistence.store_blocks import SQLBlockPersistence
    from bsentinel.infrastructure.scraping.store_guard import BlockState
    factory, (_, store_id) = schedule_db

    @asynccontextmanager
    async def context():
        async with factory() as session:
            async with session.begin():
                yield session

    persistence = SQLBlockPersistence(context)
    now = datetime(2026, 10, 8, 13, tzinfo=UTC)
    first = BlockState(now + timedelta(minutes=60), 'captcha_blocked')
    longer = BlockState(now + timedelta(minutes=70), 'challenge_blocked')
    import asyncio
    # Concurrent independent writers must converge on the maximum, not last commit.
    await asyncio.gather(*(persistence.extend(store_id, state) for state in [first, longer, first]))
    restarted = SQLBlockPersistence(context)
    assert await restarted.read(store_id) == longer
    await restarted.clear(store_id, first)
    assert await restarted.read(store_id) == longer
    await restarted.clear(store_id, longer)
    assert await restarted.read(store_id) is None


async def test_block_write_survives_catalog_rollback(schedule_db):
    from sqlalchemy import select

    from bsentinel.infrastructure.persistence.sqlalchemy.models import StoreModel
    from bsentinel.infrastructure.persistence.store_blocks import SQLBlockPersistence
    from bsentinel.infrastructure.scraping.store_guard import BlockState
    factory, (_, store_id) = schedule_db

    @asynccontextmanager
    async def context():
        async with factory() as session:
            async with session.begin():
                yield session

    persistence = SQLBlockPersistence(context)
    state = BlockState(datetime(2026, 10, 8, 14, tzinfo=UTC), 'captcha_blocked')
    async with factory() as catalog:
        await catalog.execute(select(StoreModel).where(StoreModel.id == store_id))
        await persistence.extend(store_id, state)
        await catalog.rollback()
    assert await SQLBlockPersistence(context).read(store_id) == state
