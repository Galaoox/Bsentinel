"""System routes for API v1."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from bsentinel.application.services import SystemQueryService


def build_system_router(get_service):
    router = APIRouter(prefix="/system", tags=["system"])

    @router.get("/info")
    async def api_info(service: SystemQueryService = Depends(get_service)):
        return await service.get_info()

    return router
