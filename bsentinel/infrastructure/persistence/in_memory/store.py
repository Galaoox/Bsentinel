"""Shared in-memory storage for adapters."""

from __future__ import annotations

from uuid import UUID

from bsentinel.domain.models import ArchiveJob, Book, BookStoreRelation, PriceHistoryRecord, Store


class InMemoryStore:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.stores: dict[UUID, Store] = {}
        self.books: dict[UUID, Book] = {}
        self.relations: dict[UUID, BookStoreRelation] = {}
        self.history: dict[UUID, PriceHistoryRecord] = {}
        self.archive_jobs: dict[UUID, ArchiveJob] = {}
        self.revoked_refresh_tokens: dict[str, dict] = {}
        self._seed_store()

    def _seed_store(self) -> None:
        store = Store()
        self.stores[store.id] = store
