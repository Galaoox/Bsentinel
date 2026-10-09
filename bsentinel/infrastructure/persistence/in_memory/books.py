"""In-memory book repository adapter."""

from __future__ import annotations

from uuid import UUID

from bsentinel.domain.dates import as_utc
from bsentinel.domain.models import Book

from .store import InMemoryStore


class InMemoryBookRepository:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    async def add(self, book: Book) -> None:
        self.store.books[book.id] = book

    async def get(self, book_id: UUID) -> Book | None:
        return self.store.books.get(book_id)

    async def get_by_isbn(self, isbn: str) -> Book | None:
        for book in self.store.books.values():
            if book.isbn == isbn:
                return book
        return None

    async def list(self, *, include_deleted: bool = False) -> list[Book]:
        values = self.store.books.values()
        if include_deleted:
            return list(values)
        return [book for book in values if not book.is_deleted]

    async def list_page(self, *, include_deleted: bool, q: str | None, isbn: str | None,
                        author: str | None, category: str | None,
                        page: int, limit: int) -> tuple[list[Book], int]:
        books = await self.list(include_deleted=include_deleted)
        if q:
            books = [book for book in books if q.lower() in book.title.lower()]
        if isbn:
            books = [book for book in books if book.isbn == isbn]
        if author:
            books = [book for book in books if any(author.lower() in value.lower() for value in book.authors)]
        if category:
            books = [book for book in books if any(category.lower() in value.lower() for value in book.categories)]
        books.sort(key=lambda book: (as_utc(book.created_at), book.id), reverse=True)
        start = (page - 1) * limit
        return books[start:start + limit], len(books)
