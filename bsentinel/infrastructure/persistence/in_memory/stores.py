"""In-memory store repository adapter."""

from __future__ import annotations

from uuid import UUID

from bsentinel.domain.models import Store, now_utc
from bsentinel.domain.scraping_schedule import initial_check

from .store import InMemoryStore


class InMemoryStoreRepository:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    async def add(self, store: Store) -> None:
        self.store.stores[store.id] = store

    async def save(self, store: Store) -> None:
        previous = self.store.stores.get(store.id)
        if previous and (not previous.is_active or previous.is_deleted) and store.is_active and not store.is_deleted:
            now = now_utc()
            for relation in self.store.relations.values():
                if relation.store_id == store.id and relation.scrape_group is not None:
                    relation.scrape_generation += 1
                    relation.next_check_at = initial_check(relation.scrape_group, now, relation.last_checked)
        self.store.stores[store.id] = store

    async def get(self, store_id: UUID) -> Store | None:
        return self.store.stores.get(store_id)

    async def get_by_domain(self, domain: str) -> Store | None:
        for store in self.store.stores.values():
            if store.domain == domain and not store.is_deleted:
                return store
        return None

    async def list(self) -> list[Store]:
        return [store for store in self.store.stores.values() if not store.is_deleted]
