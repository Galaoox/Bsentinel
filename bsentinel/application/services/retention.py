"""Retention application service."""

from __future__ import annotations

from dataclasses import asdict
from uuid import UUID

from bsentinel.application.ports import ArchiveJobRepositoryPort
from bsentinel.exceptions import EntityDoesNotExistError, ValidationError


class RetentionService:
    def __init__(self, *, jobs: ArchiveJobRepositoryPort) -> None:
        self.jobs = jobs

    def create_archive_job(self, older_than_days: int, min_active_records_per_book: int) -> dict:
        if older_than_days <= 0:
            raise ValidationError("older_than_days must be greater than 0")
        if min_active_records_per_book < 1:
            raise ValidationError("min_active_records_per_book must be at least 1")

        job = self.jobs.create()
        job = self.jobs.run(job.id, older_than_days, min_active_records_per_book)
        return asdict(job)

    def get_archive_job(self, job_id: UUID) -> dict:
        job = self.jobs.get(job_id)
        if not job:
            raise EntityDoesNotExistError("Archive job not found")
        return asdict(job)
