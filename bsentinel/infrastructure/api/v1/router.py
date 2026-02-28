"""API v1 router composition."""

from __future__ import annotations

from fastapi import APIRouter

from .catalog import build_catalog_router
from .pricing import build_pricing_router
from .retention import build_retention_router
from .system import build_system_router


def build_v1_router(get_system_service, get_catalog_command_service, get_catalog_query_service, get_scraping_service, get_pricing_service, get_retention_service):
    router = APIRouter(prefix="/api/v1")
    router.include_router(build_system_router(get_system_service))
    router.include_router(build_catalog_router(get_catalog_command_service, get_catalog_query_service, get_scraping_service))
    router.include_router(build_pricing_router(get_pricing_service))
    router.include_router(build_retention_router(get_retention_service))
    return router
