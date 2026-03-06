"""Catalog application services."""

from __future__ import annotations

from datetime import UTC, datetime
from math import ceil
from urllib.parse import urlparse
from uuid import UUID

from bsentinel.application.ports import (
    BookRepositoryPort,
    MetadataProviderPort,
    RelationRepositoryPort,
    ScraperPort,
    StoreRepositoryPort,
)
from bsentinel.domain.models import Book, BookStoreRelation
from bsentinel.exceptions import (
    EntityAlreadyExistsError,
    EntityDoesNotExistError,
    UnsupportedStoreError,
    ValidationError,
)


class CatalogCommandService:
    def __init__(
        self,
        *,
        books: BookRepositoryPort,
        stores: StoreRepositoryPort,
        relations: RelationRepositoryPort,
        metadata: MetadataProviderPort,
        scraper: ScraperPort,
    ) -> None:
        self.books = books
        self.stores = stores
        self.relations = relations
        self.metadata = metadata
        self.scraper = scraper

    async def create_book_from_url(self, product_url: str) -> tuple[Book, BookStoreRelation, str]:
        parsed = urlparse(product_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValidationError("Invalid URL")

        domain = parsed.netloc.lower()
        store = await self.stores.get_by_domain(domain)
        if not store or not store.is_active:
            raise UnsupportedStoreError("Unsupported store")

        details = await self.scraper.extract_book_details(product_url)
        isbn = (details.isbn or "").strip()
        if not isbn:
            raise ValidationError("ISBN is required to register a book")

        book = await self.books.get_by_isbn(isbn)
        if not book:
            book = Book(
                title=details.title,
                authors=details.authors,
                isbn=isbn,
            )
            metadata = await self.metadata.enrich_by_isbn(isbn)
            if metadata:
                book.publisher = metadata.get("publisher")
                book.publication_year = metadata.get("publication_year")
                book.language = metadata.get("language")
                book.pages = metadata.get("pages")
                book.description = metadata.get("description")
                book.image_url = metadata.get("image_url")
                book.categories = metadata.get("categories") or []
            await self.books.add(book)

        existing_relations = await self.relations.list_for_book(book.id)
        if any(relation.store_id == store.id for relation in existing_relations):
            raise EntityAlreadyExistsError("Book-store relation already exists")

        relation = BookStoreRelation(book_id=book.id, store_id=store.id, product_url=product_url)
        await self.relations.add(relation)
        return book, relation, store.domain

    async def delete_book(self, book_id: UUID) -> None:
        book = await self.books.get(book_id)
        if not book:
            raise EntityDoesNotExistError("Book not found")
        book.is_deleted = True
        book.deleted_at = datetime.now(UTC)
        await self.books.add(book)

    async def restore_book(self, book_id: UUID) -> dict:
        book = await self.books.get(book_id)
        if not book:
            raise EntityDoesNotExistError("Book not found")
        if not book.is_deleted:
            raise ValidationError("Book is not deleted")

        book.is_deleted = False
        book.deleted_at = None
        await self.books.add(book)
        return {"book_id": str(book.id), "is_deleted": book.is_deleted, "deleted_at": book.deleted_at}


class CatalogQueryService:
    def __init__(
        self,
        *,
        books: BookRepositoryPort,
        stores: StoreRepositoryPort,
        relations: RelationRepositoryPort,
    ) -> None:
        self.books = books
        self.stores = stores
        self.relations = relations

    async def list_books(
        self,
        *,
        include_deleted: bool,
        q: str | None,
        isbn: str | None,
        author: str | None,
        category: str | None,
        page: int,
        limit: int,
    ) -> dict:
        books = await self.books.list(include_deleted=include_deleted)

        if q:
            term = q.lower()
            books = [b for b in books if term in b.title.lower()]
        if isbn:
            books = [b for b in books if b.isbn == isbn]
        if author:
            term = author.lower()
            books = [b for b in books if any(term in a.lower() for a in b.authors)]
        if category:
            term = category.lower()
            books = [b for b in books if any(term in c.lower() for c in b.categories)]

        total = len(books)
        start = (page - 1) * limit
        paginated = books[start : start + limit]

        items = []
        for book in paginated:
            rels = await self.relations.list_for_book(book.id)
            relation = rels[0] if rels else None
            items.append(
                {
                    "book_id": str(book.id),
                    "title": book.title,
                    "authors": book.authors,
                    "isbn": book.isbn,
                    "is_deleted": book.is_deleted,
                    "current_price": relation.current_price if relation else None,
                    "status": relation.status if relation else "desconocido",
                }
            )

        return {
            "items": items,
            "meta": {
                "total": total,
                "page": page,
                "limit": limit,
                "pages": ceil(total / limit) if total else 0,
            },
        }

    async def get_book_detail(self, book_id: UUID) -> dict:
        book = await self.books.get(book_id)
        if not book:
            raise EntityDoesNotExistError("Book not found")

        stores = []
        for rel in await self.relations.list_for_book(book.id):
            store = await self.stores.get(rel.store_id)
            stores.append(
                {
                    "domain": store.domain if store else "unknown",
                    "price": rel.current_price,
                    "status": rel.status,
                    "last_checked": rel.last_checked,
                }
            )

        return {
            "book_id": str(book.id),
            "title": book.title,
            "authors": book.authors,
            "isbn": book.isbn,
            "is_deleted": book.is_deleted,
            "deleted_at": book.deleted_at,
            "openlibrary": {
                "publisher": book.publisher,
                "publication_year": book.publication_year,
                "language": book.language,
                "pages": book.pages,
                "description": book.description,
                "image_url": book.image_url,
                "categories": book.categories,
            },
            "stores": stores,
        }
