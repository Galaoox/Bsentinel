import importlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text

from alembic import command

ROOT_DIR = Path(__file__).resolve().parents[3]
PANAMERICANA_ID = "bd65e550-8ac8-4aee-95e7-9f5788640e29"
PANAMERICANA_DOMAIN = "www.panamericana.com.co"


def _migration_config(db_path: Path, monkeypatch) -> tuple[Config, str]:
    async_db_url = f"sqlite+aiosqlite:///{db_path}"
    sync_db_url = f"sqlite:///{db_path}"

    monkeypatch.setenv("DATABASE_URL", async_db_url)
    monkeypatch.setenv("PERSISTENCE_BACKEND", "sql")

    bsentinel_pkg = importlib.import_module("bsentinel")
    settings_module = importlib.import_module("bsentinel._settings")
    session_module = importlib.import_module("bsentinel.infrastructure.persistence.sqlalchemy.session")
    importlib.reload(settings_module)
    bsentinel_pkg.settings = settings_module.settings
    importlib.reload(session_module)
    return Config(str(ROOT_DIR / "alembic.ini")), sync_db_url


def _load_buscalibre_rules(db_url: str) -> dict:
    engine = create_engine(db_url)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text("SELECT extraction_rules FROM stores WHERE domain = :domain"),
                {"domain": "www.buscalibre.com.co"},
            ).scalar_one()
    finally:
        engine.dispose()

    if isinstance(row, str):
        return json.loads(row)
    return row


def test_buscalibre_price_normalizer_migrates_forward(tmp_path, monkeypatch):
    db_path = tmp_path / "migration_price_rules.db"
    cfg, sync_db_url = _migration_config(db_path, monkeypatch)

    command.upgrade(cfg, "0004_add_store_extraction_rules")
    rules_after_0004 = _load_buscalibre_rules(sync_db_url)
    normalizers_after_0004 = {source["normalizer"] for source in rules_after_0004["price"]["sources"]}
    assert normalizers_after_0004 == {"price_latam"}

    command.upgrade(cfg, "head")
    migrated_rules = _load_buscalibre_rules(sync_db_url)
    migrated_normalizers = {source["normalizer"] for source in migrated_rules["price"]["sources"]}
    assert migrated_normalizers == {"price_cop_mixed"}


def test_panamericana_seed_migrates_fresh_database_and_downgrades_cleanly(tmp_path, monkeypatch):
    db_path = tmp_path / "migration_panamericana_fresh.db"
    cfg, sync_db_url = _migration_config(db_path, monkeypatch)

    command.upgrade(cfg, "head")
    engine = create_engine(sync_db_url)
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                text("SELECT id, domain, extraction_rules FROM stores ORDER BY domain")
            ).mappings().all()
        assert [row["domain"] for row in rows] == [
            "www.buscalibre.com.co",
            PANAMERICANA_DOMAIN,
        ]
        panamericana = next(row for row in rows if row["domain"] == PANAMERICANA_DOMAIN)
        rules = json.loads(panamericana["extraction_rules"])
        assert panamericana["id"] == PANAMERICANA_ID
        assert rules["isbn"]["sources"][1]["kind"] == "vtex_property"

        command.downgrade(cfg, "0005_buscalibre_price_norm")
        with engine.connect() as connection:
            domains = connection.execute(text("SELECT domain FROM stores ORDER BY domain")).scalars().all()
        assert domains == ["www.buscalibre.com.co"]
    finally:
        engine.dispose()


def test_panamericana_migration_preserves_preexisting_custom_store(tmp_path, monkeypatch):
    db_path = tmp_path / "migration_panamericana_existing.db"
    cfg, sync_db_url = _migration_config(db_path, monkeypatch)
    custom_rules = {"custom": {"sources": []}}

    command.upgrade(cfg, "0005_buscalibre_price_norm")
    engine = create_engine(sync_db_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO stores (
                        id, name, domain, country_code, scrape_interval_hours,
                        is_active, extraction_rules, is_deleted, created_at, deleted_at
                    ) VALUES (
                        :id, :name, :domain, :country_code, :interval,
                        :is_active, :rules, :is_deleted, :created_at, NULL
                    )
                    """
                ),
                {
                    "id": "custom-panamericana-id",
                    "name": "Panamericana personalizada",
                    "domain": PANAMERICANA_DOMAIN,
                    "country_code": "CO",
                    "interval": 12,
                    "is_active": False,
                    "rules": json.dumps(custom_rules),
                    "is_deleted": False,
                    "created_at": datetime.now(UTC),
                },
            )

        command.upgrade(cfg, "head")
        command.downgrade(cfg, "0005_buscalibre_price_norm")
        with engine.connect() as connection:
            row = connection.execute(
                text("SELECT id, name, scrape_interval_hours, extraction_rules FROM stores WHERE domain = :domain"),
                {"domain": PANAMERICANA_DOMAIN},
            ).mappings().one()
        assert row["id"] == "custom-panamericana-id"
        assert row["name"] == "Panamericana personalizada"
        assert row["scrape_interval_hours"] == 12
        assert json.loads(row["extraction_rules"]) == custom_rules
    finally:
        engine.dispose()


def test_panamericana_downgrade_rejects_archived_history(tmp_path, monkeypatch):
    db_path = tmp_path / "migration_panamericana_history.db"
    cfg, sync_db_url = _migration_config(db_path, monkeypatch)
    now = datetime.now(UTC)

    command.upgrade(cfg, "head")
    engine = create_engine(sync_db_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO books (id, title, isbn, is_deleted, created_at, deleted_at) "
                    "VALUES ('book-id', 'Book', '9788410466456', false, :created_at, NULL)"
                ),
                {"created_at": now},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO book_store_relations (
                        id, book_id, store_id, product_url, current_price, status, last_checked, created_at
                    ) VALUES (
                        'relation-id', 'book-id', :store_id, :url, 99000, 'activo', :checked_at, :created_at
                    )
                    """
                ),
                {
                    "store_id": PANAMERICANA_ID,
                    "url": "https://www.panamericana.com.co/el-metal-perdido-730391/p",
                    "checked_at": now,
                    "created_at": now,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO price_history_archive (
                        id, book_id, relation_id, store_id, price, state, checked_at, archived
                    ) VALUES (
                        'history-id', 'book-id', 'relation-id', :store_id, 99000, 'activo', :checked_at, true
                    )
                    """
                ),
                {"store_id": PANAMERICANA_ID, "checked_at": now},
            )

        with pytest.raises(RuntimeError, match="related data exists in price_history_archive"):
            command.downgrade(cfg, "0005_buscalibre_price_norm")
        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT count(*) FROM stores WHERE id = :id"), {"id": PANAMERICANA_ID}
            ).scalar_one() == 1
            assert connection.execute(
                text("SELECT count(*) FROM price_history_archive WHERE store_id = :id"),
                {"id": PANAMERICANA_ID},
            ).scalar_one() == 1
    finally:
        engine.dispose()
