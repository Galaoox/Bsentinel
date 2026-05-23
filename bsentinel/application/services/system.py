"""System query application service."""

from __future__ import annotations

from datetime import UTC, datetime

from bsentinel.application.ports import StoreRepositoryPort

SUPPORTED_MVP_SITES = ["www.buscalibre.com.co"]


class SystemQueryService:
    def __init__(self, *, stores: StoreRepositoryPort) -> None:
        self.stores = stores

    async def get_info(self) -> dict:
        return {
            "version": "v1",
            "supported_sites": SUPPORTED_MVP_SITES.copy(),
            "updated_at": datetime.now(UTC),
        }
