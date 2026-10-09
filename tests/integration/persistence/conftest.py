"""SQL regression databases are always disposable and PostgreSQL is opt-in."""
import os
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from bsentinel.infrastructure.persistence.sqlalchemy.base import Base
from bsentinel.infrastructure.persistence.sqlalchemy.session import configure_sqlite_unicode


@pytest_asyncio.fixture(params=['sqlite', 'postgres'])
async def sql_factory(request, tmp_path):
    admin = None
    if request.param == 'postgres':
        url = os.environ.get('BULK_TEST_POSTGRES_URL')
        if not url:
            pytest.skip('BULK_TEST_POSTGRES_URL absent; disposable PostgreSQL only')
        parsed = make_url(url)
        assert parsed.host in {'127.0.0.1', 'localhost'} and parsed.database == 'bulk_test'
        schema = 'r1_' + uuid4().hex
        admin = create_async_engine(url)
        async with admin.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA {schema}'))
        engine = create_async_engine(url, connect_args={'server_settings': {'search_path': schema}})
    else:
        engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "regressions.db"}')
        configure_sqlite_unicode(engine)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        yield async_sessionmaker(engine, autoflush=False, expire_on_commit=False), engine
    finally:
        await engine.dispose()
        if admin:
            async with admin.begin() as connection:
                await connection.execute(text(f'DROP SCHEMA IF EXISTS {schema} CASCADE'))
            await admin.dispose()
