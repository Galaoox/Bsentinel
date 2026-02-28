"""ORM models for persistence layer."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


def uuid_str() -> str:
    return str(uuid4())


class StoreModel(Base):
    __tablename__ = "stores"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    country_code: Mapped[str] = mapped_column(String(3), nullable=False)
    scrape_interval_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=6)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BookModel(Base):
    __tablename__ = "books"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    isbn: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    publisher: Mapped[str | None] = mapped_column(String(255), nullable=True)
    publication_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    pages: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    authors: Mapped[list["BookAuthorModel"]] = relationship(cascade="all, delete-orphan", lazy="selectin")
    categories: Mapped[list["BookCategoryModel"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class BookAuthorModel(Base):
    __tablename__ = "book_authors"
    __table_args__ = (UniqueConstraint("book_id", "position", name="uq_book_author_position"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    book_id: Mapped[str] = mapped_column(String(36), ForeignKey("books.id", ondelete="CASCADE"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    author: Mapped[str] = mapped_column(String(255), nullable=False)


class BookCategoryModel(Base):
    __tablename__ = "book_categories"
    __table_args__ = (UniqueConstraint("book_id", "position", name="uq_book_category_position"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    book_id: Mapped[str] = mapped_column(String(36), ForeignKey("books.id", ondelete="CASCADE"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str] = mapped_column(String(255), nullable=False)


class BookStoreRelationModel(Base):
    __tablename__ = "book_store_relations"
    __table_args__ = (UniqueConstraint("book_id", "store_id", name="uq_book_store_relation"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    book_id: Mapped[str] = mapped_column(String(36), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    store_id: Mapped[str] = mapped_column(String(36), ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True)
    product_url: Mapped[str] = mapped_column(Text, nullable=False)
    current_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    last_checked: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PriceHistoryModel(Base):
    __tablename__ = "price_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    book_id: Mapped[str] = mapped_column(String(36), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    relation_id: Mapped[str] = mapped_column(String(36), ForeignKey("book_store_relations.id", ondelete="CASCADE"), nullable=False, index=True)
    store_id: Mapped[str] = mapped_column(String(36), ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    state: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class PriceHistoryArchiveModel(Base):
    __tablename__ = "price_history_archive"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    book_id: Mapped[str] = mapped_column(String(36), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    relation_id: Mapped[str] = mapped_column(String(36), ForeignKey("book_store_relations.id", ondelete="CASCADE"), nullable=False, index=True)
    store_id: Mapped[str] = mapped_column(String(36), ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    state: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ArchiveJobModel(Base):
    __tablename__ = "archive_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    moved_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errors: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
