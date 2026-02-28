"""Retention routes for API v1."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status

from bsentinel.application.services import RetentionService

from .schemas import CreateArchiveJobRequest


def build_retention_router(get_service):
    router = APIRouter(prefix="/retention", tags=["retention"])

    @router.post("/jobs/archive", status_code=status.HTTP_202_ACCEPTED)
    async def create_archive_job(
        payload: CreateArchiveJobRequest,
        service: RetentionService = Depends(get_service),
    ):
        return service.create_archive_job(
            older_than_days=payload.older_than_days,
            min_active_records_per_book=payload.min_active_records_per_book,
        )

    @router.get("/jobs/archive/{job_id}")
    async def get_archive_job(job_id: UUID, service: RetentionService = Depends(get_service)):
        return service.get_archive_job(job_id)

    return router
