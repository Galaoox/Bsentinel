from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import inspect, select

from bsentinel.domain.models import BookStoreRelation
from bsentinel.infrastructure.persistence.sqlalchemy.models import (
    BookStoreRelationModel,
)
from bsentinel.infrastructure.persistence.sqlalchemy.relations import SQLRelationRepository


async def test_schedule_roundtrip_and_group_constraint(schedule_db):
    factory, (book_id, store_id) = schedule_db
    from uuid import UUID

    relation = BookStoreRelation(book_id=UUID(book_id), store_id=UUID(store_id))
    assert hasattr(relation, "scrape_group"), "persistent schedule is missing"
    relation.scrape_group = 2
    relation.next_check_at = datetime(2026, 10, 8, 12, 40, tzinfo=UTC)
    relation.scrape_generation = 7
    async with factory() as session:
        repo = SQLRelationRepository(session)
        await repo.add(relation)
        await session.commit()
    async with factory() as session:
        loaded = (await SQLRelationRepository(session).list_all())[0]
        assert loaded.scrape_group == 2
        assert loaded.next_check_at == relation.next_check_at
        assert loaded.scrape_generation == 7
        model = await session.scalar(select(BookStoreRelationModel))
        model.scrape_group = 3
        from sqlalchemy.exc import IntegrityError

        with pytest.raises(IntegrityError):
            await session.commit()


@pytest.mark.parametrize("backend", ["sqlite", "postgres"])
def test_migration_backfills_balanced_schedule_preserves_prices(tmp_path, monkeypatch, backend):
    import os

    from alembic.config import Config
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    from alembic import command
    from bsentinel import settings

    url = f"sqlite:///{tmp_path}/migration.db"
    admin = None
    if backend == "postgres":
        pg = os.environ.get("SCHEDULE_TEST_POSTGRES_URL")
        if not pg:
            pytest.skip("Dedicated SCHEDULE_TEST_POSTGRES_URL absent")
        parsed = make_url(pg)
        assert (
            parsed.host == "127.0.0.1"
            and parsed.port != 5432
            and parsed.database == "bsentinel_schedule_test"
        )
        schema = "migration_" + uuid4().hex
        admin = create_engine(parsed.set(drivername="postgresql+psycopg2"))
        with admin.begin() as conn:
            conn.execute(text(f"CREATE SCHEMA {schema}"))
        url = (
            parsed.set(drivername="postgresql+psycopg2").render_as_string(hide_password=False)
            + f"?options=-csearch_path={schema}"
        )
    monkeypatch.setattr(settings, "database_url", url)
    config = Config("alembic.ini")
    command.upgrade(config, "0006_add_panamericana_store")
    engine = create_engine(url)
    now = datetime.now(UTC)
    with engine.begin() as conn:
        store_id = conn.execute(text("select id from stores limit 1")).scalar_one()
        import sqlalchemy as sa

        books = sa.Table("books", sa.MetaData(), autoload_with=conn)
        relations = sa.Table("book_store_relations", sa.MetaData(), autoload_with=conn)
        history = sa.Table("price_history", sa.MetaData(), autoload_with=conn)
        for i in range(8):
            book_id = str(uuid4())
            relation_id = str(uuid4())
            conn.execute(
                books.insert().values(id=book_id, title=str(i), is_deleted=False, created_at=now)
            )
            conn.execute(
                relations.insert().values(
                    id=relation_id,
                    book_id=book_id,
                    store_id=store_id,
                    product_url="https://fixture.invalid/" + str(i),
                    current_price=42,
                    status="activo",
                    last_checked=now,
                    created_at=now,
                )
            )
            conn.execute(
                history.insert().values(
                    id=str(uuid4()),
                    book_id=book_id,
                    relation_id=relation_id,
                    store_id=store_id,
                    price=42,
                    state="activo",
                    checked_at=now,
                    archived=False,
                )
            )
    command.upgrade(config, "0007_add_scraping_schedule")
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "select scrape_group,next_check_at,current_price,last_checked from book_store_relations"
            )
        ).all()
        assert all(row[0] is not None for row in rows), "backfill missing"
        assert sorted(sum(row[0] == group for row in rows) for group in range(3)) == [2, 3, 3]
        assert all(row[2] == 42 and row[3] for row in rows)
        assert conn.execute(text("select count(*) from book_store_relations where scrape_generation=0")).scalar_one() == 8
        assert (
            conn.execute(text("select count(*) from price_history where price=42")).scalar_one()
            == 8
        )
        ordered = conn.execute(
            text(
                "select scrape_group,next_check_at from book_store_relations order by created_at,id"
            )
        ).all()
        assert [row[0] for row in ordered] == [i % 3 for i in range(8)]
        from datetime import timedelta

        for group, scheduled in ordered:
            if isinstance(scheduled, str):
                scheduled = datetime.fromisoformat(scheduled)
            if scheduled.tzinfo is None:
                scheduled = scheduled.replace(tzinfo=UTC)
            assert scheduled >= now + timedelta(hours=1)
            assert scheduled.minute == group * 20
    command.downgrade(config, "0006_add_panamericana_store")
    assert "scrape_group" not in {
        c["name"] for c in inspect(engine).get_columns("book_store_relations")
    }
    assert "scrape_generation" not in {
        c["name"] for c in inspect(engine).get_columns("book_store_relations")
    }
    with engine.connect() as conn:
        assert conn.execute(text("select count(*) from book_store_relations")).scalar_one() == 8
    engine.dispose()
    if admin is not None:
        with admin.begin() as conn:
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()
