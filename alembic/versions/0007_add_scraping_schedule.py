"""Persist fixed hourly scraping phases and backfill existing relations.

Revision ID: 0007_add_scraping_schedule
Revises: 0006_add_panamericana_store
"""

from datetime import UTC, datetime, timedelta

import sqlalchemy as sa

from alembic import op

revision = "0007_add_scraping_schedule"
down_revision = "0006_add_panamericana_store"
branch_labels = None
depends_on = None


def _initial_slot(group, now, checked):
    # Freeze the calendar here so future application changes cannot alter migrations.
    if checked is not None and checked.tzinfo is None:
        checked = checked.replace(tzinfo=UTC)
    threshold = (
        max(now + timedelta(microseconds=1), checked + timedelta(hours=1))
        if checked
        else now + timedelta(microseconds=1)
    )
    slot = threshold.astimezone(UTC).replace(minute=group * 20, second=0, microsecond=0)
    return slot if slot >= threshold else slot + timedelta(hours=1)


def upgrade():
    with op.batch_alter_table("book_store_relations") as batch:
        batch.add_column(sa.Column("scrape_group", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("next_check_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("scrape_generation", sa.Integer(), nullable=False, server_default="0"))
        batch.create_check_constraint("ck_relation_scrape_group", "scrape_group BETWEEN 0 AND 2")
        batch.create_index("ix_book_store_relations_next_check_at", ["next_check_at"])
    bind = op.get_bind()
    table = sa.table(
        "book_store_relations",
        sa.column("id", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("last_checked", sa.DateTime(timezone=True)),
        sa.column("scrape_group", sa.Integer()),
        sa.column("next_check_at", sa.DateTime(timezone=True)),
    )
    now = datetime.now(UTC)
    rows = bind.execute(
        sa.select(table.c.id, table.c.last_checked).order_by(table.c.created_at, table.c.id)
    ).all()
    for index, row in enumerate(rows):
        group = index % 3
        bind.execute(
            table.update()
            .where(table.c.id == row.id)
            .values(scrape_group=group, next_check_at=_initial_slot(group, now, row.last_checked))
        )


def downgrade():
    with op.batch_alter_table("book_store_relations") as batch:
        batch.drop_index("ix_book_store_relations_next_check_at")
        batch.drop_constraint("ck_relation_scrape_group", type_="check")
        batch.drop_column("next_check_at")
        batch.drop_column("scrape_generation")
        batch.drop_column("scrape_group")
