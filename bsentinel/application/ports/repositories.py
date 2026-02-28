"""Application repository ports."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from bsentinel.domain.models import ArchiveJob, Book, BookStoreRelation, PriceHistoryRecord, Store


class BookRepositoryPort(Protocol):
    def add(self, book: Book) -> None: ...

    def get(self, book_id: UUID) -> Book | None: ...

    def get_by_source_url(self, source_url: str) -> Book | None: ...

    def list(self, *, include_deleted: bool = False) -> list[Book]: ...


class StoreRepositoryPort(Protocol):
    def get(self, store_id: UUID) -> Store | None: ...

    def get_by_domain(self, domain: str) -> Store | None: ...

    def list(self) -> list[Store]: ...


class RelationRepositoryPort(Protocol):
    def add(self, relation: BookStoreRelation) -> None: ...

    def list_for_book(self, book_id: UUID) -> list[BookStoreRelation]: ...

    def list_all(self) -> list[BookStoreRelation]: ...


class HistoryRepositoryPort(Protocol):
    def add(self, record: PriceHistoryRecord) -> None: ...

    def list(
        self,
        *,
        book_id: UUID,
        source: str,
        state: str | None,
        start_date: datetime | None,
        end_date: datetime | None,
    ) -> list[PriceHistoryRecord]: ...


class ArchiveJobRepositoryPort(Protocol):
    def create(self) -> ArchiveJob: ...

    def get(self, job_id: UUID) -> ArchiveJob | None: ...

    def run(self, job_id: UUID, older_than_days: int, min_active_records_per_book: int) -> ArchiveJob: ...
