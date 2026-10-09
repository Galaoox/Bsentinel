import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect


def test_0008_upgrade_downgrade_is_additive(tmp_path):
    path = Path("alembic/versions/0008_add_scraping_traffic.py")
    assert path.exists(), "new migration required; never edit applied 0007"
    spec = importlib.util.spec_from_file_location("traffic_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.down_revision == "0007_add_scraping_schedule"
    engine = create_engine(f"sqlite:///{tmp_path}/migration.db")
    with engine.begin() as conn:
        migration.op = Operations(MigrationContext.configure(conn))
        migration.upgrade()
        assert "scraping_traffic_events" in inspect(conn).get_table_names()
        indexes = inspect(conn).get_indexes("scraping_traffic_events")
        assert {i["name"] for i in indexes} == {"ix_traffic_date_scope", "ix_traffic_batch_date"}
        migration.downgrade()
        assert "scraping_traffic_events" not in inspect(conn).get_table_names()
    engine.dispose()


async def test_0008_roundtrip_on_isolated_database(schedule_db):
    from bsentinel.infrastructure.persistence.sqlalchemy.traffic_model import TrafficEventModel

    factory, _ = schedule_db
    path = Path("alembic/versions/0008_add_scraping_traffic.py")
    spec = importlib.util.spec_from_file_location("traffic_migration_isolated", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    async with factory() as session:
        conn = await session.connection()

        def exercise(sync):
            TrafficEventModel.__table__.drop(sync)
            migration.op = Operations(MigrationContext.configure(sync))
            migration.upgrade()
            columns = {c["name"] for c in inspect(sync).get_columns("scraping_traffic_events")}
            assert columns == set(TrafficEventModel.__table__.columns.keys())
            migration.downgrade()
            assert "scraping_traffic_events" not in inspect(sync).get_table_names()

        await conn.run_sync(exercise)
