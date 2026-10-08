"""In-memory relation repository adapter."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from uuid import UUID

from bsentinel.domain.models import BookStoreRelation, now_utc
from bsentinel.domain.scraping_schedule import initial_check

from .store import InMemoryStore


class InMemoryRelationRepository:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    async def get(self, relation_id: UUID) -> BookStoreRelation | None:
        return deepcopy(self.store.relations.get(relation_id))

    async def add(self, relation: BookStoreRelation) -> None:
        # No await between count/assignment/add: serialized by this process event loop.
        if relation.scrape_group is None:
            counts = [0, 0, 0]
            for current in self.store.relations.values():
                book = self.store.books.get(current.book_id)
                store = self.store.stores.get(current.store_id)
                if book and not book.is_deleted and store and store.is_active and not store.is_deleted and current.scrape_group is not None:
                    counts[current.scrape_group] += 1
            relation.scrape_group = min(range(3), key=lambda group: (counts[group], group))
        if relation.next_check_at is None:
            relation.next_check_at = initial_check(relation.scrape_group, now_utc(), relation.last_checked)
        self.store.relations[relation.id] = relation

    async def save(self, relation: BookStoreRelation) -> None:
        previous = self.store.relations.get(relation.id)
        if previous and previous.product_url != relation.product_url and relation.scrape_group is not None:
            relation.scrape_generation = previous.scrape_generation + 1
            relation.next_check_at = initial_check(relation.scrape_group, now_utc(), relation.last_checked)
        self.store.relations[relation.id] = relation

    async def list_for_book(self, book_id: UUID) -> list[BookStoreRelation]:
        return [rel for rel in self.store.relations.values() if rel.book_id == book_id]

    async def list_due(self, now: datetime, limit: int, after: tuple[datetime, UUID] | None = None) -> list[BookStoreRelation]:
        if limit < 1:
            raise ValueError("limit must be positive")
        eligible = []
        for relation in self.store.relations.values():
            book = self.store.books.get(relation.book_id)
            store = self.store.stores.get(relation.store_id)
            if not book or book.is_deleted or not store or store.is_deleted or not store.is_active:
                continue
            if relation.next_check_at is None or relation.next_check_at > now:
                continue
            if after and (relation.next_check_at, str(relation.id)) <= (after[0], str(after[1])):
                continue
            eligible.append(relation)
        return sorted(eligible, key=lambda r: (r.next_check_at, str(r.id)))[:limit]

    async def list_all(self) -> list[BookStoreRelation]:
        return list(self.store.relations.values())
