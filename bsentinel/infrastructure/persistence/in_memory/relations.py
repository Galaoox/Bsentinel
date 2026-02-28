"""In-memory relation repository adapter."""

from __future__ import annotations

from uuid import UUID

from bsentinel.domain.models import BookStoreRelation

from .store import InMemoryStore


class InMemoryRelationRepository:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    async def add(self, relation: BookStoreRelation) -> None:
        self.store.relations[relation.id] = relation

    async def save(self, relation: BookStoreRelation) -> None:
        self.store.relations[relation.id] = relation

    async def list_for_book(self, book_id: UUID) -> list[BookStoreRelation]:
        return [rel for rel in self.store.relations.values() if rel.book_id == book_id]

    async def list_all(self) -> list[BookStoreRelation]:
        return list(self.store.relations.values())
