"""Seed Panamericana Colombia with extraction rules.

Revision ID: 0006_add_panamericana_store
Revises: 0005_buscalibre_price_norm
Create Date: 2026-10-07 00:00:00
"""

from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0006_add_panamericana_store"
down_revision = "0005_buscalibre_price_norm"
branch_labels = None
depends_on = None

PANAMERICANA_ID = "bd65e550-8ac8-4aee-95e7-9f5788640e29"
PANAMERICANA_DOMAIN = "www.panamericana.com.co"
PANAMERICANA_RULES = {
    "title": {
        "sources": [
            {"kind": "json_ld", "path": "name", "normalizer": "text_trim"},
            {"kind": "css", "selector": "h1", "attribute": "text", "normalizer": "text_trim"},
        ]
    },
    "authors": {
        "sources": [
            {"kind": "json_ld", "path": "author[].name", "normalizer": "text_trim"},
            {"kind": "vtex_property", "path": "Autor", "normalizer": "text_trim"},
        ]
    },
    "isbn": {
        "sources": [
            {"kind": "json_ld", "path": "isbn", "normalizer": "isbn_digits"},
            {"kind": "vtex_property", "path": "ISBN", "normalizer": "isbn_digits"},
        ]
    },
    "price": {
        "sources": [
            {"kind": "json_ld", "path": "offers.lowPrice", "normalizer": "price_cop_mixed"},
            {"kind": "json_ld", "path": "offers.offers[].price", "normalizer": "price_cop_mixed"},
        ]
    },
    "availability": {
        "sources": [
            {
                "kind": "json_ld",
                "path": "offers.offers[].availability",
                "normalizer": "availability_buscalibre",
            }
        ]
    },
}


def _json_type(bind) -> sa.JSON:
    return postgresql.JSONB(astext_type=sa.Text()) if bind.dialect.name == "postgresql" else sa.JSON()


def _stores_table(bind) -> sa.Table:
    return sa.table(
        "stores",
        sa.column("id", sa.String()),
        sa.column("name", sa.String()),
        sa.column("domain", sa.String()),
        sa.column("country_code", sa.String()),
        sa.column("scrape_interval_hours", sa.Integer()),
        sa.column("is_active", sa.Boolean()),
        sa.column("extraction_rules", _json_type(bind)),
        sa.column("is_deleted", sa.Boolean()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("deleted_at", sa.DateTime(timezone=True)),
    )


def upgrade() -> None:
    bind = op.get_bind()
    stores = _stores_table(bind)
    existing = bind.execute(
        sa.select(stores.c.id).where(stores.c.domain == PANAMERICANA_DOMAIN)
    ).first()
    if existing:
        return

    bind.execute(
        stores.insert().values(
            id=PANAMERICANA_ID,
            name="Panamericana",
            domain=PANAMERICANA_DOMAIN,
            country_code="CO",
            scrape_interval_hours=6,
            is_active=True,
            extraction_rules=PANAMERICANA_RULES,
            is_deleted=False,
            created_at=datetime.now(UTC),
            deleted_at=None,
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    stores = _stores_table(bind)
    seeded = bind.execute(
        sa.select(stores.c.id).where(
            stores.c.id == PANAMERICANA_ID,
            stores.c.domain == PANAMERICANA_DOMAIN,
        )
    ).first()
    if not seeded:
        return

    dependent_tables = ("price_history_archive", "price_history", "book_store_relations")
    for table_name in dependent_tables:
        table = sa.table(table_name, sa.column("store_id", sa.String()))
        if bind.execute(
            sa.select(sa.func.count()).select_from(table).where(table.c.store_id == PANAMERICANA_ID)
        ).scalar_one():
            raise RuntimeError(
                f"Cannot downgrade Panamericana seed while related data exists in {table_name}"
            )

    bind.execute(stores.delete().where(stores.c.id == PANAMERICANA_ID))
