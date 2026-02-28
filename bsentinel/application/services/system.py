"""System query application service."""

from __future__ import annotations

from datetime import UTC, datetime

from bsentinel.application.ports import StoreRepositoryPort


class SystemQueryService:
    def __init__(self, *, stores: StoreRepositoryPort) -> None:
        self.stores = stores

    def get_info(self) -> dict:
        return {
            "version": "v1",
            "supported_sites": [store.domain for store in self.stores.list()],
            "updated_at": datetime.now(UTC),
        }
