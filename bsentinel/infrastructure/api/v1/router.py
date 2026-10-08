"""API v1 router composition."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from .auth import build_auth_router, build_authenticated_dependency
from .catalog import build_catalog_router
from .pricing import build_pricing_router
from .retention import build_retention_router
from .system import build_system_router


def build_v1_router(
    get_system_service,
    get_catalog_command_service,
    get_catalog_query_service,
    get_scraping_service,
    get_pricing_service,
    get_retention_service,
    get_auth_service,
):
    router = APIRouter(prefix="/api/v1")
    protected_dependencies = [Depends(build_authenticated_dependency(get_auth_service))]

    router.include_router(build_auth_router(get_auth_service))
    router.include_router(build_system_router(get_system_service), dependencies=protected_dependencies)
    router.include_router(
        build_catalog_router(get_catalog_command_service, get_catalog_query_service, get_scraping_service),
        dependencies=protected_dependencies,
    )
    router.include_router(build_pricing_router(get_pricing_service), dependencies=protected_dependencies)
    router.include_router(build_retention_router(get_retention_service), dependencies=protected_dependencies)
    return router
