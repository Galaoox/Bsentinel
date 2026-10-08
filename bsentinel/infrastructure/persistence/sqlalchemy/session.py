"""Session and engine helpers for SQLAlchemy async backend."""

from __future__ import annotations

from collections.abc import AsyncIterator

from bsentinel import settings
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def configure_sqlite_unicode(engine: AsyncEngine) -> None:
    if engine.dialect.name == "sqlite":
        event.listen(engine.sync_engine, "connect", _sqlite_unicode_lower)


def _sqlite_unicode_lower(connection, _record) -> None:
    connection.create_function(
        "lower", 1, lambda value: str(value).lower() if value is not None else None,
        deterministic=True,
    )


def get_async_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            future=True,
        )
        configure_sqlite_unicode(_engine)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_async_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


async def session_scope() -> AsyncIterator[AsyncSession]:
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            if not session.info.get("bulk_owns_transaction"):
                await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_alembic_database_url() -> str:
    """Convert async SQLAlchemy URL to a sync URL suitable for Alembic."""
    db_url = settings.database_url
    if db_url.startswith("postgresql+asyncpg://"):
        return db_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    if db_url.startswith("sqlite+aiosqlite://"):
        return db_url.replace("sqlite+aiosqlite://", "sqlite://", 1)
    return db_url


async def dispose_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
