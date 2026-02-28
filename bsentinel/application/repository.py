"""Repositorio en memoria para MVP local/dev."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from uuid import UUID

from bsentinel.domain.models import ArchiveJob, Book, BookStoreRelation, PriceHistoryRecord, Store, now_utc


class InMemoryRepository:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.stores: dict[UUID, Store] = {}
        self.books: dict[UUID, Book] = {}
        self.relations: dict[UUID, BookStoreRelation] = {}
        self.history: dict[UUID, PriceHistoryRecord] = {}
        self.archive_jobs: dict[UUID, ArchiveJob] = {}
        self._seed_store()

    def _seed_store(self) -> None:
        store = Store()
        self.stores[store.id] = store

    def get_store_by_domain(self, domain: str) -> Store | None:
        for store in self.stores.values():
            if store.domain == domain and not store.is_deleted:
                return store
        return None

    def list_stores(self) -> list[Store]:
        return [store for store in self.stores.values() if not store.is_deleted]

    def add_book(self, book: Book) -> None:
        self.books[book.id] = book

    def add_relation(self, relation: BookStoreRelation) -> None:
        self.relations[relation.id] = relation

    def add_history(self, record: PriceHistoryRecord) -> None:
        self.history[record.id] = record

    def get_book_by_source_url(self, source_url: str) -> Book | None:
        for book in self.books.values():
            if book.source_url == source_url:
                return book
        return None

    def get_book(self, book_id: UUID) -> Book | None:
        return self.books.get(book_id)

    def list_books(self, include_deleted: bool = False) -> list[Book]:
        values = self.books.values()
        if include_deleted:
            return list(values)
        return [book for book in values if not book.is_deleted]

    def get_relations_for_book(self, book_id: UUID) -> list[BookStoreRelation]:
        return [rel for rel in self.relations.values() if rel.book_id == book_id]

    def get_store(self, store_id: UUID) -> Store | None:
        return self.stores.get(store_id)

    def list_history(
        self,
        *,
        book_id: UUID,
        source: str,
        state: str | None,
        start_date: datetime | None,
        end_date: datetime | None,
    ) -> list[PriceHistoryRecord]:
        records = [r for r in self.history.values() if r.book_id == book_id]
        if source == "active":
            records = [r for r in records if not r.archived]
        elif source == "archive":
            records = [r for r in records if r.archived]
        if state:
            records = [r for r in records if r.state == state]
        if start_date:
            records = [r for r in records if r.checked_at >= start_date]
        if end_date:
            records = [r for r in records if r.checked_at <= end_date]
        records.sort(key=lambda r: r.checked_at, reverse=True)
        return records

    def create_archive_job(self) -> ArchiveJob:
        job = ArchiveJob()
        self.archive_jobs[job.id] = job
        return job

    def get_archive_job(self, job_id: UUID) -> ArchiveJob | None:
        return self.archive_jobs.get(job_id)

    def run_archive_job(self, job_id: UUID, older_than_days: int, min_active_records_per_book: int) -> ArchiveJob:
        job = self.archive_jobs[job_id]
        job.status = "running"
        job.started_at = now_utc()

        try:
            cutoff = now_utc() - timedelta(days=older_than_days)
            by_book: dict[UUID, list[PriceHistoryRecord]] = defaultdict(list)
            for record in self.history.values():
                if not record.archived:
                    by_book[record.book_id].append(record)

            moved = 0
            for records in by_book.values():
                records.sort(key=lambda r: r.checked_at, reverse=True)
                keep_ids = {r.id for r in records[:min_active_records_per_book]}
                for record in records[min_active_records_per_book:]:
                    if record.checked_at < cutoff and record.id not in keep_ids:
                        record.archived = True
                        moved += 1

            job.moved_records = moved
            job.status = "completed"
        except Exception as exc:  # pragma: no cover - safety net
            job.errors.append(str(exc))
            job.status = "failed"
        finally:
            job.finished_at = now_utc()

        return job
