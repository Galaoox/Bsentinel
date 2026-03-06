"""Add revoked refresh tokens table.

Revision ID: 0002_add_revoked_refresh_tokens
Revises: 0001_initial_schema
Create Date: 2026-03-05 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0002_add_revoked_refresh_tokens"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "revoked_refresh_tokens",
        sa.Column("jti", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("username", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_revoked_refresh_tokens_username",
        "revoked_refresh_tokens",
        ["username"],
        unique=False,
    )
    op.create_index(
        "ix_revoked_refresh_tokens_expires_at",
        "revoked_refresh_tokens",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_revoked_refresh_tokens_expires_at", table_name="revoked_refresh_tokens")
    op.drop_index("ix_revoked_refresh_tokens_username", table_name="revoked_refresh_tokens")
    op.drop_table("revoked_refresh_tokens")
