"""Update Buscalibre price normalizer to price_cop_mixed.

Revision ID: 0005_buscalibre_price_norm
Revises: 0004_add_store_extraction_rules
Create Date: 2026-03-12 00:10:00
"""

from __future__ import annotations

import copy
import json

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0005_buscalibre_price_norm"
down_revision = "0004_add_store_extraction_rules"
branch_labels = None
depends_on = None

BUSCALIBRE_DOMAIN = "www.buscalibre.com.co"
LEGACY_NORMALIZER = "price_latam"
NEW_NORMALIZER = "price_cop_mixed"


def _json_type(bind) -> sa.JSON:
    return postgresql.JSONB(astext_type=sa.Text()) if bind.dialect.name == "postgresql" else sa.JSON()


def _coerce_rules(value):
    if isinstance(value, dict):
        return copy.deepcopy(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def _rewrite_normalizer(extraction_rules: dict, from_normalizer: str, to_normalizer: str) -> dict | None:
    updated = copy.deepcopy(extraction_rules)
    price_rules = updated.get("price")
    if not isinstance(price_rules, dict):
        return None

    sources = price_rules.get("sources")
    if not isinstance(sources, list):
        return None

    changed = False
    for source in sources:
        if isinstance(source, dict) and source.get("normalizer") == from_normalizer:
            source["normalizer"] = to_normalizer
            changed = True

    return updated if changed else None


def _update_buscalibre_rules(from_normalizer: str, to_normalizer: str) -> None:
    bind = op.get_bind()
    stores = sa.table(
        "stores",
        sa.column("id", sa.String()),
        sa.column("domain", sa.String()),
        sa.column("extraction_rules", _json_type(bind)),
    )

    rows = bind.execute(
        sa.select(stores.c.id, stores.c.extraction_rules).where(stores.c.domain == BUSCALIBRE_DOMAIN)
    ).mappings()

    for row in rows:
        rules = _coerce_rules(row["extraction_rules"])
        if rules is None:
            continue
        rewritten = _rewrite_normalizer(rules, from_normalizer, to_normalizer)
        if rewritten is None:
            continue
        bind.execute(
            stores.update().where(stores.c.id == row["id"]).values(extraction_rules=rewritten)
        )


def upgrade() -> None:
    _update_buscalibre_rules(LEGACY_NORMALIZER, NEW_NORMALIZER)


def downgrade() -> None:
    _update_buscalibre_rules(NEW_NORMALIZER, LEGACY_NORMALIZER)
