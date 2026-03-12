"""Store administration routes for API v1."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status

from bsentinel.application.services import StoreCommandService, StoreQueryService

from .schemas import StoreCreateRequest, StorePatchRequest, StoreUpdateRequest


def build_store_router(get_command_service, get_query_service):
    router = APIRouter(prefix="/stores", tags=["stores"])

    @router.post("", status_code=status.HTTP_201_CREATED)
    async def create_store(
        payload: StoreCreateRequest,
        command_service: StoreCommandService = Depends(get_command_service),
    ):
        return await command_service.create_store(**payload.model_dump(exclude_none=True))

    @router.get("")
    async def list_stores(query_service: StoreQueryService = Depends(get_query_service)):
        return await query_service.list_stores()

    @router.get("/{store_id}")
    async def get_store(store_id: UUID, query_service: StoreQueryService = Depends(get_query_service)):
        return await query_service.get_store(store_id)

    @router.put("/{store_id}")
    async def update_store(
        store_id: UUID,
        payload: StoreUpdateRequest,
        command_service: StoreCommandService = Depends(get_command_service),
    ):
        return await command_service.update_store(store_id, **payload.model_dump(exclude_none=True))

    @router.patch("/{store_id}")
    async def patch_store(
        store_id: UUID,
        payload: StorePatchRequest,
        command_service: StoreCommandService = Depends(get_command_service),
    ):
        return await command_service.patch_store(store_id, **payload.model_dump())

    return router
