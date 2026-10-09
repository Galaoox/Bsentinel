import importlib.util
from datetime import UTC, datetime
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    inspect,
    select,
)


def test_0009_additive_policy_transition_preserves_observations(tmp_path):
    path = Path('alembic/versions/0009_store_blocks_daily_windows.py')
    assert path.exists(), 'additive 0009 migration is required'
    spec = importlib.util.spec_from_file_location('blocks_migration', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.down_revision == '0008_add_scraping_traffic'
    engine = create_engine(f'sqlite:///{tmp_path}/migration.db')
    metadata = MetaData()
    Table('stores', metadata, Column('id', String(36), primary_key=True))
    relations = Table('book_store_relations', metadata,
                      Column('id', String(36), primary_key=True), Column('scrape_group', Integer),
                      Column('next_check_at', DateTime(timezone=True)), Column('scrape_generation', Integer),
                      Column('last_checked', DateTime(timezone=True)), Column('current_price', Integer))
    now = datetime(2026, 10, 8, 18, tzinfo=UTC)
    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return now
    migration.datetime = FrozenDatetime
    with engine.begin() as conn:
        metadata.create_all(conn)
        conn.execute(relations.insert(), [
            {'id': str(i), 'scrape_group': i % 3, 'next_check_at': now if i < 3 else None,
             'scrape_generation': 5, 'last_checked': now, 'current_price': 123} for i in range(4)
        ])
        migration.op = Operations(MigrationContext.configure(conn))
        migration.upgrade()
        rows = conn.execute(select(relations).order_by(relations.c.id)).mappings().all()
        for i, row in enumerate(rows):
            assert row['current_price'] == 123
            assert row['last_checked'] == now.replace(tzinfo=None)
            if i < 3:
                assert row['next_check_at'] == now.replace(hour=22, minute=i * 20, tzinfo=None)
                assert row['scrape_generation'] == 6
            else:
                assert row['next_check_at'] is None
                assert row['scrape_generation'] == 5
        assert 'scraping_store_blocks' in inspect(conn).get_table_names()
        migration.downgrade()
        assert 'scraping_store_blocks' not in inspect(conn).get_table_names()
        # Rollback never rewrites observations or historical timestamps.
        assert conn.execute(select(relations)).mappings().all() == rows
    engine.dispose()


async def test_full_alembic_chain_policy_transition_is_idempotent_on_restart(schedule_db, monkeypatch):
    from alembic.config import Config
    from sqlalchemy import create_engine, text

    from alembic import command
    from bsentinel import settings
    from bsentinel.infrastructure.persistence.sqlalchemy.base import Base
    factory, _ = schedule_db
    engine = factory.kw['bind']
    async with engine.begin() as conn:
        schema = await conn.scalar(text('SELECT current_schema()')) if engine.dialect.name == 'postgresql' else None
        await conn.run_sync(Base.metadata.drop_all)
    url = engine.url.set(drivername='postgresql+psycopg2' if schema else 'sqlite')
    if schema:
        url = url.update_query_dict({'options': '-csearch_path=' + schema})
    assert url.host in {None, '127.0.0.1'}
    assert url.port != 5432
    migration_url = url.set(query={}).render_as_string(hide_password=False)
    if schema:
        migration_url += '?options=-csearch_path=' + schema
    monkeypatch.setattr(settings, 'database_url', migration_url)
    config = Config('alembic.ini')
    command.upgrade(config, '0008_add_scraping_traffic')
    sync = create_engine(url)
    now = datetime(2026, 10, 8, 18, tzinfo=UTC)
    with sync.begin() as conn:
        stores = Table('stores', MetaData(), autoload_with=conn)
        books = Table('books', MetaData(), autoload_with=conn)
        relations = Table('book_store_relations', MetaData(), autoload_with=conn)
        store_id = conn.execute(select(stores.c.id)).first()[0]
        conn.execute(books.insert().values(id='fixture-book', title='fixture', created_at=now, is_deleted=False))
        conn.execute(relations.insert().values(id='fixture-relation', book_id='fixture-book', store_id=store_id,
                     product_url='https://fixture.invalid/book', status='activo', current_price=123,
                     last_checked=now, created_at=now, scrape_group=1, next_check_at=now, scrape_generation=5))
    command.upgrade(config, 'head')
    with sync.connect() as conn:
        before = conn.execute(text('SELECT next_check_at,scrape_generation,last_checked,current_price FROM book_store_relations')).one()
        assert before[1] == 6
        assert before[3] == 123
        assert conn.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == '0010_merge_audit_scraping'
        assert 'scraping_store_blocks' in inspect(conn).get_table_names()
    command.upgrade(config, 'head')
    with sync.connect() as conn:
        assert conn.execute(text('SELECT next_check_at,scrape_generation,last_checked,current_price FROM book_store_relations')).one() == before
    command.downgrade(config, '0008_add_scraping_traffic')
    with sync.connect() as conn:
        assert 'scraping_store_blocks' not in inspect(conn).get_table_names()
        assert conn.execute(text('SELECT next_check_at,scrape_generation,last_checked,current_price FROM book_store_relations')).one() == before
    sync.dispose()
