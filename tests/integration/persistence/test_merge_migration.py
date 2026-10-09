"""Real Alembic upgrades from either supported history preserve catalog observations."""

import logging.config
import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.engine import make_url

from alembic import command

HEAD = "0010_merge_audit_scraping"


@pytest.fixture(params=["sqlite", "postgres"])
def migration_database(request, tmp_path, monkeypatch):
    from bsentinel.infrastructure.persistence.sqlalchemy import session as session_module

    # Alembic's CLI logging setup must not disable pytest's existing loggers.
    monkeypatch.setattr(logging.config, "fileConfig", lambda *args, **kwargs: None)
    admin = None
    url = f"sqlite:///{tmp_path}/merge.db"
    if request.param == "postgres":
        pg = os.environ.get("SCHEDULE_TEST_POSTGRES_URL")
        if not pg:
            pytest.skip("Dedicated SCHEDULE_TEST_POSTGRES_URL absent")
        parsed = make_url(pg)
        assert parsed.host == "127.0.0.1" and parsed.port != 5432
        assert parsed.database == "bsentinel_schedule_test"
        schema = "merge_" + uuid4().hex
        admin = sa.create_engine(parsed.set(drivername="postgresql+psycopg2"))
        with admin.begin() as conn:
            conn.execute(sa.text(f"CREATE SCHEMA {schema}"))
        url = (parsed.set(drivername="postgresql+psycopg2").render_as_string(hide_password=False)
               + "?options=-csearch_path=" + schema)
    monkeypatch.setattr(session_module.settings, "database_url", url)
    engine = sa.create_engine(url)
    try:
        yield Config("alembic.ini"), engine
    finally:
        engine.dispose()
        if admin is not None:
            with admin.begin() as conn:
                conn.execute(sa.text(f"DROP SCHEMA {schema} CASCADE"))
            admin.dispose()


@pytest.mark.parametrize("source", ["base", "0007_normalize_isbn", "0009_store_blocks_daily_windows"])
def test_merge_upgrade_preserves_data_and_applies_only_pending_transforms(migration_database, source):
    config, engine = migration_database
    assert ScriptDirectory.from_config(config).get_heads() == [HEAD]
    # Seed at the last common schema so both independent data migrations see real legacy rows.
    command.upgrade(config, "0006_add_panamericana_store")
    spellings = ["978-0-13-449416-6", "9780132350884", "978-0-13-235088-4", "invalid", "", "0-8044-2957-x"]
    normalized = ["9780134494166", *spellings[1:5], "080442957X"]
    now = datetime(2026, 10, 8, 18, tzinfo=UTC)
    with engine.begin() as conn:
        metadata = sa.MetaData()
        books = sa.Table("books", metadata, autoload_with=conn)
        authors = sa.Table("book_authors", metadata, autoload_with=conn)
        categories = sa.Table("book_categories", metadata, autoload_with=conn)
        relations = sa.Table("book_store_relations", metadata, autoload_with=conn)
        history = sa.Table("price_history", metadata, autoload_with=conn)
        archive = sa.Table("price_history_archive", metadata, autoload_with=conn)
        store_id = conn.execute(sa.text("SELECT id FROM stores LIMIT 1")).scalar_one()
        for i, isbn in enumerate(spellings):
            book_id, relation_id = f"book-{i}", f"relation-{i}"
            conn.execute(books.insert().values(id=book_id, isbn=isbn, title=f"Book {i}", created_at=now, is_deleted=False))
            conn.execute(authors.insert().values(book_id=book_id, position=0, author=f"Author {i}"))
            conn.execute(categories.insert().values(book_id=book_id, position=0, category=f"Category {i}"))
            conn.execute(relations.insert().values(id=relation_id, book_id=book_id, store_id=store_id,
                         product_url=f"https://fixture.invalid/{i}", current_price=123 + i, status="activo",
                         last_checked=now, created_at=now))
            observation = dict(id=f"history-{i}", book_id=book_id, relation_id=relation_id, store_id=store_id,
                               price=100 + i, state="activo", checked_at=now, archived=False)
            conn.execute(history.insert().values(**observation))
            # Archive has its own identity/timestamp but retains the original observation.
            archive_columns = set(archive.c.keys())
            archived = {key: value for key, value in observation.items() if key in archive_columns}
            archived["id"] = f"archive-{i}"
            if "archived_at" in archive_columns:
                archived["archived_at"] = now
            conn.execute(archive.insert().values(**archived))
    if source != "base":
        command.upgrade(config, source)
    def read_catalog(conn):
        return {
            name: conn.execute(sa.text(f"SELECT * FROM {name} ORDER BY id")).mappings().all()
            for name in ("books", "book_authors", "book_categories", "book_store_relations", "price_history", "price_history_archive")
        }
    with engine.connect() as conn:
        before = read_catalog(conn)
    command.upgrade(config, "head")
    with engine.connect() as conn:
        after = read_catalog(conn)
        assert conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one() == HEAD
        assert "scraping_store_blocks" in sa.inspect(conn).get_table_names()
        assert [row["isbn"] for row in after["books"]] == normalized
        # Only ISBN spelling may change in books; no catalog/observation rows disappear.
        assert [{k: v for k, v in row.items() if k != "isbn"} for row in after["books"]] == [
            {k: v for k, v in row.items() if k != "isbn"} for row in before["books"]
        ]
        for name in ("book_authors", "book_categories", "price_history", "price_history_archive"):
            assert after[name] == before[name]
        for old, new in zip(before["book_store_relations"], after["book_store_relations"], strict=True):
            assert {k: v for k, v in new.items() if k not in {"scrape_group", "next_check_at", "scrape_generation"}} == {
                k: v for k, v in old.items() if k not in {"scrape_group", "next_check_at", "scrape_generation"}
            }
            if source == "0009_store_blocks_daily_windows":
                assert new == old  # Already applied calendars/generations must never rebase.
            else:
                scheduled = new["next_check_at"]
                if isinstance(scheduled, str):
                    scheduled = datetime.fromisoformat(scheduled)
                if scheduled.tzinfo is None:
                    scheduled = scheduled.replace(tzinfo=UTC)
                from zoneinfo import ZoneInfo
                local = scheduled.astimezone(ZoneInfo("America/Bogota"))
                assert local.hour in {8, 17} and local.minute == new["scrape_group"] * 20
                assert new["scrape_generation"] == 1
    command.upgrade(config, "head")
    with engine.connect() as conn:
        assert read_catalog(conn) == after


def test_merge_upgrade_from_empty_database(migration_database):
    config, engine = migration_database
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    with engine.connect() as conn:
        assert conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one() == HEAD
        assert conn.execute(sa.text("SELECT count(*) FROM books")).scalar_one() == 0
        assert {"book_store_relations", "price_history", "scraping_traffic_events", "scraping_store_blocks"} <= set(
            sa.inspect(conn).get_table_names()
        )
