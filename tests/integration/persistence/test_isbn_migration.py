import importlib.util
import logging
from datetime import UTC, datetime
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import func, select

from bsentinel.infrastructure.persistence.sqlalchemy.models import (
    BookModel,
    BookStoreRelationModel,
    PriceHistoryModel,
    StoreModel,
)
from bsentinel.infrastructure.scraping.rules import build_default_buscalibre_rules


async def test_isbn_migration_preserves_collisions_deleted_invalid_and_custom_rules(sql_factory, monkeypatch, caplog):
    factory, engine = sql_factory
    now = datetime.now(UTC)
    values = ['978-0-132-35088-4', '9780132350884', '978-0-134-49416-6',
              '0-8044-2957-x', '9780132350885', None, '', '0132350882']
    ids = [str(uuid4()) for _ in values]
    store_id = str(uuid4())
    custom_id = str(uuid4())
    rules = build_default_buscalibre_rules()
    rules['isbn']['sources'][1]['regex'] = r'(97[89]\d{10}|\d{9}[\dXx])'
    custom = {'isbn': {'sources': [{'kind': 'css', 'selector': '.custom', 'attribute': 'text',
                                   'regex': r'ISBN:\s*([0-9-]+)', 'normalizer': 'isbn_digits'}]}}
    relation_id, history_id = str(uuid4()), str(uuid4())
    async with factory.begin() as session:
        session.add_all([BookModel(id=key, title='Fixture', isbn=isbn, created_at=now,
                                   is_deleted=index == 0) for index, (key, isbn) in enumerate(zip(ids, values))])
        session.add_all([StoreModel(id=key, name='Fixture', domain=domain, country_code='CO',
                                    created_at=now, extraction_rules=extraction)
                         for key, domain, extraction in [(store_id, 'fixture.invalid', rules),
                                                         (custom_id, 'custom.invalid', custom)]])
        await session.flush()
        session.add(BookStoreRelationModel(id=relation_id, book_id=ids[0], store_id=store_id,
                                            product_url='https://fixture.invalid', status='activo', created_at=now))
        await session.flush()
        session.add(PriceHistoryModel(id=history_id, book_id=ids[0], store_id=store_id,
                                      relation_id=relation_id, price=1, state='activo', checked_at=now))
    from pathlib import Path
    spec = importlib.util.spec_from_file_location('isbn_migration', Path('alembic/versions/0007_normalize_isbn.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    def upgrade(connection):
        monkeypatch.setattr(module, 'op', Operations(MigrationContext.configure(connection)))
        module.upgrade()
    with caplog.at_level(logging.WARNING, logger='alembic.runtime.migration'):
        async with engine.begin() as connection:
            await connection.run_sync(upgrade)
    async with factory() as session:
        actual = dict((await session.execute(select(BookModel.id, BookModel.isbn))).all())
        assert [actual[key] for key in ids] == [values[0], values[1], '9780134494166',
                                                '080442957X', values[4], None, '', '0132350882']
        assert (await session.get(StoreModel, custom_id)).extraction_rules == custom
        pattern = (await session.get(StoreModel, store_id)).extraction_rules['isbn']['sources'][1]['regex']
        assert pattern == module.ISBN_REGEX
        assert await session.scalar(select(func.count()).select_from(BookStoreRelationModel)) == 1
        assert (await session.get(BookStoreRelationModel, relation_id)).book_id == ids[0]
        assert (await session.get(PriceHistoryModel, history_id)).relation_id == relation_id
    logs = caplog.text
    assert 'reason=conflict count=2' in logs and ids[0] in logs and ids[1] in logs
    assert 'reason=invalid count=1' in logs and 'reason=empty count=2' in logs
    # Downgrade cannot reconstruct spelling and must leave relational data untouched.
    module.downgrade()
