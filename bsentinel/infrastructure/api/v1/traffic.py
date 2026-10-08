"""Authenticated read-only traffic report."""

from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from .auth import build_authenticated_dependency


def build_traffic_router(get_repository, get_auth_service):
    router = APIRouter(
        prefix="/api/v1/metrics",
        tags=["metrics"],
        dependencies=[Depends(build_authenticated_dependency(get_auth_service))],
    )

    @router.get("/traffic")
    async def traffic_report(
        start: datetime | None = None,
        end: datetime | None = None,
        relation_count: int | None = Query(None, ge=0, le=1000000),
        scope: Literal["periodic", "manual", "catalog", "unattributed"] | None = None,
        batch_id: UUID | None = None,
        repository=Depends(get_repository),
    ):
        end = end or datetime.now(UTC)
        start = start or end - timedelta(days=30)
        if (
            start.tzinfo is None
            or end.tzinfo is None
            or not start < end
            or end - start > timedelta(days=366)
        ):
            raise HTTPException(422, "Use timezone-aware start < end, at most 366 days")
        return await repository.report(
            start.astimezone(UTC),
            end.astimezone(UTC),
            relation_count=relation_count,
            scope=scope,
            batch_id=str(batch_id) if batch_id else None,
        )

    return router
