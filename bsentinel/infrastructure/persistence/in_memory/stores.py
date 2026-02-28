"""In-memory store repository adapter."""

from __future__ import annotations

from uuid import UUID

from bsentinel.domain.models import Store

from .store import InMemoryStore


class InMemoryStoreRepository:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    async def get(self, store_id: UUID) -> Store | None:
        return self.store.stores.get(store_id)

    async def get_by_domain(self, domain: str) -> Store | None:
        for store in self.store.stores.values():
            if store.domain == domain and not store.is_deleted:
                return store
        return None

    async def list(self) -> list[Store]:
        return [store for store in self.store.stores.values() if not store.is_deleted]
