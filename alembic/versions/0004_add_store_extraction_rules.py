"""Add persisted extraction rules to stores.

Revision ID: 0004_add_store_extraction_rules
Revises: 0003_remove_book_source_url
Create Date: 2026-03-06 00:30:00
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0004_add_store_extraction_rules"
down_revision = "0003_remove_book_source_url"
branch_labels = None
depends_on = None

BUSCALIBRE_RULES = {
    "title": {
        "sources": [
            {"kind": "json_ld", "path": "name", "normalizer": "text_trim"},
            {"kind": "css", "selector": "h1", "attribute": "text", "normalizer": "text_trim"},
            {
                "kind": "css",
                "selector": "meta[property='og:title']",
                "attribute": "content",
                "normalizer": "text_trim",
            },
        ]
    },
    "authors": {
        "sources": [
            {"kind": "json_ld", "path": "author[].name", "normalizer": "text_trim"},
            {"kind": "css", "selector": ".author a", "attribute": "text", "normalizer": "text_trim"},
        ]
    },
    "isbn": {
        "sources": [
            {"kind": "json_ld", "path": "isbn", "normalizer": "isbn_digits"},
            {
                "kind": "css",
                "selector": "body",
                "attribute": "text",
                "regex": "(97[89]\\d{10}|\\d{9}[\\dXx])",
                "normalizer": "isbn_digits",
            },
        ]
    },
    "price": {
        "sources": [
            {"kind": "json_ld", "path": "offers[].price", "normalizer": "price_latam"},
            {
                "kind": "css",
                "selector": "meta[property='product:price:amount']",
                "attribute": "content",
                "normalizer": "price_latam",
            },
            {"kind": "css", "selector": ".precio-ahora", "attribute": "text", "normalizer": "price_latam"},
        ]
    },
    "availability": {
        "sources": [
            {"kind": "json_ld", "path": "offers[].availability", "normalizer": "availability_buscalibre"},
            {"kind": "css", "selector": "body", "attribute": "text", "normalizer": "availability_buscalibre"},
        ]
    },
}


def upgrade() -> None:
    bind = op.get_bind()
    json_type = postgresql.JSONB(astext_type=sa.Text()) if bind.dialect.name == "postgresql" else sa.JSON()
    stores_table = sa.table(
        "stores",
        sa.column("domain", sa.String()),
        sa.column("extraction_rules", json_type),
    )

    op.add_column("stores", sa.Column("extraction_rules", json_type, nullable=True))
    op.execute(
        stores_table.update()
        .where(stores_table.c.domain == "www.buscalibre.com.co")
        .values(extraction_rules=BUSCALIBRE_RULES)
    )
    op.execute(
        stores_table.update()
        .where(stores_table.c.extraction_rules.is_(None))
        .values(extraction_rules=BUSCALIBRE_RULES)
    )
    with op.batch_alter_table("stores") as batch_op:
        batch_op.alter_column("extraction_rules", existing_type=json_type, nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("stores") as batch_op:
        batch_op.drop_column("extraction_rules")
