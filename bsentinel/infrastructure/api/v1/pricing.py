"""Pricing routes for API v1."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from bsentinel.application.services import PricingQueryService

from .common import to_datetime


def build_pricing_router(get_service):
    router = APIRouter(prefix="/pricing", tags=["pricing"])

    @router.get("/books/{book_id}/history")
    async def get_history(
        book_id: UUID,
        source: str = Query(default="all", pattern="^(active|archive|all)$"),
        state: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        page: int = Query(default=1, ge=1),
        limit: int = Query(default=50, ge=1, le=200),
        service: PricingQueryService = Depends(get_service),
    ):
        return await service.get_history(
            book_id=book_id,
            source=source,
            state=state,
            start_date=to_datetime(start_date),
            end_date=to_datetime(end_date, end_of_day=True),
            page=page,
            limit=limit,
        )

    @router.get("/books/{book_id}/comparison")
    async def price_comparison(book_id: UUID, service: PricingQueryService = Depends(get_service)):
        return await service.get_price_comparison(book_id)

    return router
