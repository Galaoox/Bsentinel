"""Independent, short transactions for store blocks (never catalog sessions)."""

from datetime import UTC

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from bsentinel.infrastructure.persistence.sqlalchemy.models import StoreBlockModel
from bsentinel.infrastructure.scraping.store_guard import BlockState


class SQLBlockPersistence:
    def __init__(self, context):
        self.context = context

    async def read(self, store_id):
        async with self.context() as session:
            row = await session.get(StoreBlockModel, str(store_id))
            if row is None:
                return None
            until = row.blocked_until
            if until.tzinfo is None:
                until = until.replace(tzinfo=UTC)
            return BlockState(until.astimezone(UTC), row.reason)

    async def extend(self, store_id, state):
        async with self.context() as session:
            insert = pg_insert if session.bind.dialect.name == 'postgresql' else sqlite_insert
            statement = insert(StoreBlockModel).values(
                store_id=str(store_id), blocked_until=state.blocked_until, reason=state.reason,
            )
            statement = statement.on_conflict_do_update(
                index_elements=['store_id'],
                set_={'blocked_until': statement.excluded.blocked_until, 'reason': statement.excluded.reason},
                where=StoreBlockModel.blocked_until <= statement.excluded.blocked_until,
            )
            await session.execute(statement)
            row = (await session.execute(select(StoreBlockModel).where(StoreBlockModel.store_id == str(store_id)))).scalar_one()
            until = row.blocked_until
            if until.tzinfo is None:
                until = until.replace(tzinfo=UTC)
            saved = BlockState(until.astimezone(UTC), row.reason)
        return saved

    async def clear(self, store_id, observed):
        async with self.context() as session:
            await session.execute(delete(StoreBlockModel).where(
                StoreBlockModel.store_id == str(store_id),
                StoreBlockModel.blocked_until == observed.blocked_until,
                StoreBlockModel.reason == observed.reason,
            ))
