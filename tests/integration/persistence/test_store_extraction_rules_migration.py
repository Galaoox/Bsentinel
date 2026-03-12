import importlib
import json
from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, text

from alembic import command

ROOT_DIR = Path(__file__).resolve().parents[3]


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

    cfg = Config(str(ROOT_DIR / "alembic.ini"))

    command.upgrade(cfg, "0004_add_store_extraction_rules")
    rules_after_0004 = _load_buscalibre_rules(sync_db_url)
    normalizers_after_0004 = {source["normalizer"] for source in rules_after_0004["price"]["sources"]}
    assert normalizers_after_0004 == {"price_latam"}

    command.upgrade(cfg, "head")
    migrated_rules = _load_buscalibre_rules(sync_db_url)
    migrated_normalizers = {source["normalizer"] for source in migrated_rules["price"]["sources"]}
    assert migrated_normalizers == {"price_cop_mixed"}
