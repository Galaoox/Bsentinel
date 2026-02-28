"""Initial persistence schema and default store seed.

Revision ID: 0001_initial_schema
Revises: None
Create Date: 2026-02-28 00:00:00
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stores",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("country_code", sa.String(length=3), nullable=False),
        sa.Column("scrape_interval_hours", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("domain", name="uq_stores_domain"),
    )

    op.create_table(
        "books",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("isbn", sa.String(length=20), nullable=True),
        sa.Column("publisher", sa.String(length=255), nullable=True),
        sa.Column("publication_year", sa.Integer(), nullable=True),
        sa.Column("language", sa.String(length=10), nullable=True),
        sa.Column("pages", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("source_url", name="uq_books_source_url"),
    )
    op.create_index("ix_books_isbn", "books", ["isbn"], unique=False)

    op.create_table(
        "book_authors",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("book_id", sa.String(length=36), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("author", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("book_id", "position", name="uq_book_author_position"),
    )

    op.create_table(
        "book_categories",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("book_id", sa.String(length=36), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("book_id", "position", name="uq_book_category_position"),
    )

    op.create_table(
        "book_store_relations",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("book_id", sa.String(length=36), nullable=False),
        sa.Column("store_id", sa.String(length=36), nullable=False),
        sa.Column("product_url", sa.Text(), nullable=False),
        sa.Column("current_price", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("last_checked", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("book_id", "store_id", name="uq_book_store_relation"),
    )
    op.create_index(
        "ix_book_store_relations_book_id", "book_store_relations", ["book_id"], unique=False
    )
    op.create_index(
        "ix_book_store_relations_store_id", "book_store_relations", ["store_id"], unique=False
    )

    op.create_table(
        "price_history",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("book_id", sa.String(length=36), nullable=False),
        sa.Column("relation_id", sa.String(length=36), nullable=False),
        sa.Column("store_id", sa.String(length=36), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("state", sa.String(length=50), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["relation_id"], ["book_store_relations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_price_history_book_id", "price_history", ["book_id"], unique=False)
    op.create_index("ix_price_history_relation_id", "price_history", ["relation_id"], unique=False)
    op.create_index("ix_price_history_store_id", "price_history", ["store_id"], unique=False)
    op.create_index("ix_price_history_state", "price_history", ["state"], unique=False)
    op.create_index("ix_price_history_checked_at", "price_history", ["checked_at"], unique=False)

    op.create_table(
        "price_history_archive",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("book_id", sa.String(length=36), nullable=False),
        sa.Column("relation_id", sa.String(length=36), nullable=False),
        sa.Column("store_id", sa.String(length=36), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("state", sa.String(length=50), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["relation_id"], ["book_store_relations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_price_history_archive_book_id", "price_history_archive", ["book_id"], unique=False
    )
    op.create_index(
        "ix_price_history_archive_relation_id", "price_history_archive", ["relation_id"], unique=False
    )
    op.create_index(
        "ix_price_history_archive_store_id", "price_history_archive", ["store_id"], unique=False
    )
    op.create_index(
        "ix_price_history_archive_state", "price_history_archive", ["state"], unique=False
    )
    op.create_index(
        "ix_price_history_archive_checked_at", "price_history_archive", ["checked_at"], unique=False
    )

    op.create_table(
        "archive_jobs",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("moved_records", sa.Integer(), nullable=False),
        sa.Column("errors", sa.Text(), nullable=False),
    )

    now = datetime.now(timezone.utc)
    op.execute(
        sa.text(
            """
            INSERT INTO stores (id, name, domain, country_code, scrape_interval_hours, is_active, is_deleted, created_at, deleted_at)
            VALUES (:id, :name, :domain, :country_code, :interval, :is_active, :is_deleted, :created_at, :deleted_at)
            """
        ).bindparams(
            id=str(uuid4()),
            name="Buscalibre",
            domain="www.buscalibre.com.co",
            country_code="CO",
            interval=6,
            is_active=True,
            is_deleted=False,
            created_at=now,
            deleted_at=None,
        )
    )


def downgrade() -> None:
    op.drop_table("archive_jobs")

    op.drop_index("ix_price_history_archive_checked_at", table_name="price_history_archive")
    op.drop_index("ix_price_history_archive_state", table_name="price_history_archive")
    op.drop_index("ix_price_history_archive_store_id", table_name="price_history_archive")
    op.drop_index("ix_price_history_archive_relation_id", table_name="price_history_archive")
    op.drop_index("ix_price_history_archive_book_id", table_name="price_history_archive")
    op.drop_table("price_history_archive")

    op.drop_index("ix_price_history_checked_at", table_name="price_history")
    op.drop_index("ix_price_history_state", table_name="price_history")
    op.drop_index("ix_price_history_store_id", table_name="price_history")
    op.drop_index("ix_price_history_relation_id", table_name="price_history")
    op.drop_index("ix_price_history_book_id", table_name="price_history")
    op.drop_table("price_history")

    op.drop_index("ix_book_store_relations_store_id", table_name="book_store_relations")
    op.drop_index("ix_book_store_relations_book_id", table_name="book_store_relations")
    op.drop_table("book_store_relations")

    op.drop_table("book_categories")
    op.drop_table("book_authors")

    op.drop_index("ix_books_isbn", table_name="books")
    op.drop_table("books")

    op.drop_table("stores")
