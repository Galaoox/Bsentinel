"""Remove book source_url and keep product URLs on relations only.

Revision ID: 0003_remove_book_source_url
Revises: 0002_add_revoked_refresh_tokens
Create Date: 2026-03-06 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0003_remove_book_source_url"
down_revision = "0002_add_revoked_refresh_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("books") as batch_op:
        batch_op.drop_constraint("uq_books_source_url", type_="unique")
        batch_op.drop_column("source_url")


def downgrade() -> None:
    with op.batch_alter_table("books") as batch_op:
        batch_op.add_column(sa.Column("source_url", sa.Text(), nullable=True))
        batch_op.create_unique_constraint("uq_books_source_url", ["source_url"])
