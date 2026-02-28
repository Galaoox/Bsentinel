"""Router v1 para el MVP."""

from __future__ import annotations

from datetime import date, datetime, time, UTC
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from bsentinel.application.services import BookService
from bsentinel.exceptions import EntityAlreadyExistsError, EntityDoesNotExistError, UnsupportedStoreError, ValidationError


class CreateBookRequest(BaseModel):
    url: str = Field(min_length=10)


class ArchiveJobRequest(BaseModel):
    target: str = "price_history"
    older_than_days: int = Field(default=365, ge=1)
    min_active_records_per_book: int = Field(default=1000, ge=1)


def _to_datetime(day: date | None, end_of_day: bool = False) -> datetime | None:
    if not day:
        return None
    clock = time.max if end_of_day else time.min
    return datetime.combine(day, clock).replace(tzinfo=UTC)


def build_v1_router(get_service):
    router = APIRouter(prefix="/api/v1", tags=["v1"])

    @router.get("/info", tags=["system"])
    async def api_info(service: BookService = Depends(get_service)):
        stores = [store.domain for store in service.repository.list_stores()]
        return {
            "version": "v1",
            "supported_sites": stores,
            "updated_at": datetime.now(UTC),
        }

    @router.post("/books", status_code=status.HTTP_201_CREATED, tags=["books"])
    async def create_book(payload: CreateBookRequest, service: BookService = Depends(get_service)):
        try:
            book, relation = await service.create_book_from_url(payload.url)
        except (ValidationError, UnsupportedStoreError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except EntityAlreadyExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        return {
            "book_id": str(book.id),
            "relation_id": str(relation.id),
            "isbn": book.isbn,
            "title": book.title,
            "authors": book.authors,
            "site": "www.buscalibre.com.co",
            "status": relation.status,
        }

    @router.get("/books", tags=["books"])
    async def list_books(
        include_deleted: bool = False,
        q: str | None = None,
        isbn: str | None = None,
        author: str | None = None,
        category: str | None = None,
        page: int = Query(default=1, ge=1),
        limit: int = Query(default=50, ge=1, le=200),
        service: BookService = Depends(get_service),
    ):
        return service.list_books(
            include_deleted=include_deleted,
            q=q,
            isbn=isbn,
            author=author,
            category=category,
            page=page,
            limit=limit,
        )

    @router.get("/books/{book_id}", tags=["books"])
    async def get_book(book_id: UUID, service: BookService = Depends(get_service)):
        try:
            return service.get_book_detail(book_id)
        except EntityDoesNotExistError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.delete("/books/{book_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["books"])
    async def delete_book(book_id: UUID, service: BookService = Depends(get_service)):
        try:
            service.delete_book(book_id)
        except EntityDoesNotExistError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/books/{book_id}/restore", tags=["books"])
    async def restore_book(book_id: UUID, service: BookService = Depends(get_service)):
        try:
            return service.restore_book(book_id)
        except EntityDoesNotExistError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValidationError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.get("/books/{book_id}/history", tags=["history"])
    async def get_history(
        book_id: UUID,
        source: str = Query(default="all", pattern="^(active|archive|all)$"),
        state: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        page: int = Query(default=1, ge=1),
        limit: int = Query(default=50, ge=1, le=200),
        service: BookService = Depends(get_service),
    ):
        try:
            return service.get_history(
                book_id=book_id,
                source=source,
                state=state,
                start_date=_to_datetime(start_date),
                end_date=_to_datetime(end_date, end_of_day=True),
                page=page,
                limit=limit,
            )
        except EntityDoesNotExistError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/books/{book_id}/price-comparison", tags=["history"])
    async def price_comparison(book_id: UUID, service: BookService = Depends(get_service)):
        try:
            return service.get_price_comparison(book_id)
        except EntityDoesNotExistError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/retention/archive-jobs", status_code=status.HTTP_202_ACCEPTED, tags=["retention"])
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

    @router.get("/retention/archive-jobs/{job_id}", tags=["retention"])
    async def get_archive_job(job_id: UUID, service: BookService = Depends(get_service)):
        try:
            return service.get_archive_job(job_id)
        except EntityDoesNotExistError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    return router
