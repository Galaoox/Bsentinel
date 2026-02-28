"""System routes for API v1."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from bsentinel.application.services import BookService


def build_system_router(get_service):
    router = APIRouter(tags=["system"])

    @router.get("/info")
    async def api_info(service: BookService = Depends(get_service)):
        stores = [store.domain for store in service.repository.list_stores()]
        return {
            "version": "v1",
            "supported_sites": stores,
            "updated_at": datetime.now(UTC),
        }

    return router
