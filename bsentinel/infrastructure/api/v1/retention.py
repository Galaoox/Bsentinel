"""Retention routes for API v1."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from bsentinel.application.services import BookService
from bsentinel.exceptions import EntityDoesNotExistError, ValidationError

from .schemas import ArchiveJobRequest


def build_retention_router(get_service):
    router = APIRouter(tags=["retention"])

    @router.post("/retention/archive-jobs", status_code=status.HTTP_202_ACCEPTED)
    async def create_archive_job(payload: ArchiveJobRequest, service: BookService = Depends(get_service)):
        if payload.target != "price_history":
            raise HTTPException(status_code=400, detail="Solo se soporta target=price_history")

        try:
            return service.create_archive_job(
                older_than_days=payload.older_than_days,
                min_active_records_per_book=payload.min_active_records_per_book,
            )
        except ValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/retention/archive-jobs/{job_id}")
    async def get_archive_job(job_id: UUID, service: BookService = Depends(get_service)):
        try:
            return service.get_archive_job(job_id)
        except EntityDoesNotExistError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    return router
