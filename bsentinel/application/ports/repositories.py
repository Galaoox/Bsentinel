"""Application repository ports."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from bsentinel.domain.models import ArchiveJob, Book, BookStoreRelation, PriceHistoryRecord, Store


class BookRepositoryPort(Protocol):
    async def add(self, book: Book) -> None: ...

    async def get(self, book_id: UUID) -> Book | None: ...

    async def get_by_isbn(self, isbn: str) -> Book | None: ...

    async def list(self, *, include_deleted: bool = False) -> list[Book]: ...


class StoreRepositoryPort(Protocol):
    async def add(self, store: Store) -> None: ...

    async def save(self, store: Store) -> None: ...

    async def get(self, store_id: UUID) -> Store | None: ...

    async def get_by_domain(self, domain: str) -> Store | None: ...

    async def list(self) -> list[Store]: ...


class RelationRepositoryPort(Protocol):
    async def add(self, relation: BookStoreRelation) -> None: ...

    async def save(self, relation: BookStoreRelation) -> None: ...

    async def list_for_book(self, book_id: UUID) -> list[BookStoreRelation]: ...

    async def list_all(self) -> list[BookStoreRelation]: ...


class HistoryRepositoryPort(Protocol):
    async def add(self, record: PriceHistoryRecord) -> None: ...

    async def list(
        self,
        *,
        book_id: UUID,
        source: str,
        state: str | None,
        start_date: datetime | None,
        end_date: datetime | None,
    ) -> list[PriceHistoryRecord]: ...


class ArchiveJobRepositoryPort(Protocol):
    async def create(self) -> ArchiveJob: ...

    async def get(self, job_id: UUID) -> ArchiveJob | None: ...

    async def run(self, job_id: UUID, older_than_days: int, min_active_records_per_book: int) -> ArchiveJob: ...
