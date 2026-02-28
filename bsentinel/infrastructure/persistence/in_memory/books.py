"""In-memory book repository adapter."""

from __future__ import annotations

from uuid import UUID

from bsentinel.domain.models import Book

from .store import InMemoryStore


class InMemoryBookRepository:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    async def add(self, book: Book) -> None:
        self.store.books[book.id] = book

    async def get(self, book_id: UUID) -> Book | None:
        return self.store.books.get(book_id)

    async def get_by_source_url(self, source_url: str) -> Book | None:
        for book in self.store.books.values():
            if book.source_url == source_url:
                return book
        return None

    async def list(self, *, include_deleted: bool = False) -> list[Book]:
        values = self.store.books.values()
        if include_deleted:
            return list(values)
        return [book for book in values if not book.is_deleted]
