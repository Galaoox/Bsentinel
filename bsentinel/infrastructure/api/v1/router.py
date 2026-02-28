"""API v1 router composition."""

from __future__ import annotations

from fastapi import APIRouter

from .books import build_books_router
from .history import build_history_router
from .retention import build_retention_router
from .system import build_system_router


def build_v1_router(get_service):
    router = APIRouter(prefix="/api/v1")
    router.include_router(build_system_router(get_service))
    router.include_router(build_books_router(get_service))
    router.include_router(build_history_router(get_service))
    router.include_router(build_retention_router(get_service))
    return router
