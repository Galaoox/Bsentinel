"""In-memory archive job repository adapter."""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from uuid import UUID

from bsentinel.domain.models import ArchiveJob, PriceHistoryRecord, now_utc

from .store import InMemoryStore


class InMemoryArchiveJobRepository:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def create(self) -> ArchiveJob:
        job = ArchiveJob()
        self.store.archive_jobs[job.id] = job
        return job

    def get(self, job_id: UUID) -> ArchiveJob | None:
        return self.store.archive_jobs.get(job_id)

    def run(self, job_id: UUID, older_than_days: int, min_active_records_per_book: int) -> ArchiveJob:
        job = self.store.archive_jobs[job_id]
        job.status = "running"
        job.started_at = now_utc()

        try:
            cutoff = now_utc() - timedelta(days=older_than_days)
            by_book: dict[UUID, list[PriceHistoryRecord]] = defaultdict(list)
            for record in self.store.history.values():
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
        except Exception as exc:  # pragma: no cover
            job.errors.append(str(exc))
            job.status = "failed"
        finally:
            job.finished_at = now_utc()

        return job
