"""Price history routes for API v1."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from bsentinel.application.services import BookService
from bsentinel.exceptions import EntityDoesNotExistError

from .common import to_datetime


def build_history_router(get_service):
    router = APIRouter(tags=["history"])

    @router.get("/books/{book_id}/history")
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
                start_date=to_datetime(start_date),
                end_date=to_datetime(end_date, end_of_day=True),
                page=page,
                limit=limit,
            )
        except EntityDoesNotExistError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/books/{book_id}/price-comparison")
    async def price_comparison(book_id: UUID, service: BookService = Depends(get_service)):
        try:
            return service.get_price_comparison(book_id)
        except EntityDoesNotExistError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    return router
