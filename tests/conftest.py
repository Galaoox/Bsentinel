import asyncio
import importlib
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient

from alembic import command

# Ensure local package import works under `uv run pytest` without editable install.
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

TEST_DB_PATH = Path("/tmp/bsentinel_test.db")


class FakeConfiguredScraper:
    async def extract_book_details(self, store, product_url: str):
        slug = product_url.rstrip("/").split("/")[-1]
        title = slug.replace("-isbn-", " ").replace("-", " ").title()
        isbn = None
        marker = "isbn-"
        if marker in product_url:
            isbn = product_url.split(marker, 1)[1].split("/")[0].split("-")[0]
        return type(
            "BookDetails",
            (),
            {
                "title": title or f"Untitled Book From {store.name}",
                "authors": ["Test Author"],
                "isbn": isbn,
            },
        )()

    async def scrape_book(self, store, product_url: str):
        return type(
            "ScrapeResult",
            (),
            {
                "price": 42.5,
                "status": "activo",
                "checked_at": datetime.now(timezone.utc),
            },
        )()


class FakeMetadataProvider:
    async def enrich_by_isbn(self, isbn: str) -> dict:
        return {}



def _reset_database() -> None:
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()

    cfg = Config(str(ROOT_DIR / "alembic.ini"))
    command.upgrade(cfg, "head")


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("PERSISTENCE_BACKEND", "sql")
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{TEST_DB_PATH}")

    bsentinel_pkg = importlib.import_module("bsentinel")
    settings_module = importlib.import_module("bsentinel._settings")
    root_app_module = importlib.import_module("bsentinel.infrastructure.api.root_app")
    session_module = importlib.import_module("bsentinel.infrastructure.persistence.sqlalchemy.session")

    importlib.reload(settings_module)
    bsentinel_pkg.settings = settings_module.settings
    importlib.reload(session_module)
    root_app_module = importlib.reload(root_app_module)

    root_app_module.scraper_client = FakeConfiguredScraper()
    root_app_module.metadata_client = FakeMetadataProvider()

    _reset_database()
    with TestClient(root_app_module.root_app) as test_client:
        yield test_client
    asyncio.run(session_module.dispose_engine())
