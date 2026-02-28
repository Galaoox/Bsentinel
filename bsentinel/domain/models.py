"""Modelos de dominio para el MVP de bsentinel."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

ACTIVE = "activo"
UNKNOWN = "desconocido"


def now_utc() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True)
class Store:
    id: UUID = field(default_factory=uuid4)
    name: str = "Buscalibre"
    domain: str = "www.buscalibre.com.co"
    country_code: str = "CO"
    scrape_interval_hours: int = 6
    is_active: bool = True
    is_deleted: bool = False
    created_at: datetime = field(default_factory=now_utc)
    deleted_at: datetime | None = None


@dataclass(slots=True)
class Book:
    id: UUID = field(default_factory=uuid4)
    title: str = ""
    authors: list[str] = field(default_factory=list)
    isbn: str | None = None
    categories: list[str] = field(default_factory=list)
    publisher: str | None = None
    publication_year: int | None = None
    language: str | None = None
    pages: int | None = None
    description: str | None = None
    image_url: str | None = None
    source_url: str = ""
    is_deleted: bool = False
    created_at: datetime = field(default_factory=now_utc)
    deleted_at: datetime | None = None


@dataclass(slots=True)
class BookStoreRelation:
    id: UUID = field(default_factory=uuid4)
    book_id: UUID = field(default_factory=uuid4)
    store_id: UUID = field(default_factory=uuid4)
    product_url: str = ""
    current_price: float | None = None
    status: str = UNKNOWN
    last_checked: datetime | None = None
    created_at: datetime = field(default_factory=now_utc)


@dataclass(slots=True)
class PriceHistoryRecord:
    id: UUID = field(default_factory=uuid4)
    book_id: UUID = field(default_factory=uuid4)
    relation_id: UUID = field(default_factory=uuid4)
    store_id: UUID = field(default_factory=uuid4)
    price: float = 0.0
    state: str = UNKNOWN
    checked_at: datetime = field(default_factory=now_utc)
    archived: bool = False


@dataclass(slots=True)
class ArchiveJob:
    id: UUID = field(default_factory=uuid4)
    status: str = "queued"
    started_at: datetime | None = None
    finished_at: datetime | None = None
    moved_records: int = 0
    errors: list[str] = field(default_factory=list)
