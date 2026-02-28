"""Casos de uso del MVP."""

from __future__ import annotations

import re
from dataclasses import asdict
from datetime import UTC, datetime
from math import ceil
from urllib.parse import parse_qs, urlparse
from uuid import UUID

from bsentinel.application.repository import InMemoryRepository
from bsentinel.domain.models import Book, BookStoreRelation, PriceHistoryRecord
from bsentinel.exceptions import (
    EntityAlreadyExistsError,
    EntityDoesNotExistError,
    UnsupportedStoreError,
    ValidationError,
)
from bsentinel.infrastructure.openlibrary import OpenLibraryClient
from bsentinel.infrastructure.scraping.buscalibre import BuscalibreScraper

BUSCALIBRE_DOMAINS = {"www.buscalibre.com.co", "buscalibre.com.co"}
ISBN_PATTERN = re.compile(r"\b(97[89]\d{10}|\d{9}[\dXx])\b")


class BookService:
    def __init__(
        self,
        repository: InMemoryRepository,
        scraper: BuscalibreScraper,
        openlibrary: OpenLibraryClient,
    ) -> None:
        self.repository = repository
        self.scraper = scraper
        self.openlibrary = openlibrary

    async def create_book_from_url(self, product_url: str) -> tuple[Book, BookStoreRelation]:
        parsed = urlparse(product_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValidationError("URL inválida")

        domain = parsed.netloc.lower()
        if domain not in BUSCALIBRE_DOMAINS:
            raise UnsupportedStoreError("Tienda no soportada")

        if self.repository.get_book_by_source_url(product_url):
            raise EntityAlreadyExistsError("El libro ya existe en el sistema")

        store = self.repository.get_store_by_domain("www.buscalibre.com.co")
        if not store or not store.is_active:
            raise UnsupportedStoreError("Tienda no soportada")

        title, authors, isbn = self._extract_book_identity(product_url)
        book = Book(title=title, authors=authors, isbn=isbn, source_url=product_url)

        if isbn:
            metadata = await self.openlibrary.enrich_by_isbn(isbn)
            if metadata:
                book.publisher = metadata.get("publisher")
                book.publication_year = metadata.get("publication_year")
                book.language = metadata.get("language")
                book.pages = metadata.get("pages")
                book.description = metadata.get("description")
                book.image_url = metadata.get("image_url")
                book.categories = metadata.get("categories") or []

        self.repository.add_book(book)
        relation = BookStoreRelation(book_id=book.id, store_id=store.id, product_url=product_url)
        self.repository.add_relation(relation)
        await self.scrape_relation(relation)
        return book, relation

    async def scrape_relation(self, relation: BookStoreRelation) -> None:
        result = await self.scraper.scrape_book(relation.product_url)
        relation.current_price = result.price
        relation.status = result.status
        relation.last_checked = result.checked_at
        record = PriceHistoryRecord(
            book_id=relation.book_id,
            relation_id=relation.id,
            store_id=relation.store_id,
            price=result.price,
            state=result.status,
            checked_at=result.checked_at,
        )
        self.repository.add_history(record)

    async def scrape_all_active(self) -> int:
        total = 0
        for relation in list(self.repository.relations.values()):
            book = self.repository.get_book(relation.book_id)
            if book and not book.is_deleted:
                await self.scrape_relation(relation)
                total += 1
        return total

    def list_books(
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
        books = self.repository.list_books(include_deleted=include_deleted)

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
            relations = self.repository.get_relations_for_book(book.id)
            relation = relations[0] if relations else None
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

    def get_book_detail(self, book_id: UUID) -> dict:
        book = self.repository.get_book(book_id)
        if not book:
            raise EntityDoesNotExistError("Libro no encontrado")

        relations = self.repository.get_relations_for_book(book.id)
        stores = []
        for rel in relations:
            store = self.repository.get_store(rel.store_id)
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

    def delete_book(self, book_id: UUID) -> None:
        book = self.repository.get_book(book_id)
        if not book:
            raise EntityDoesNotExistError("Libro no encontrado")
        book.is_deleted = True
        book.deleted_at = datetime.now(UTC)

    def restore_book(self, book_id: UUID) -> dict:
        book = self.repository.get_book(book_id)
        if not book:
            raise EntityDoesNotExistError("Libro no encontrado")
        if not book.is_deleted:
            raise ValidationError("El libro no está eliminado")
        book.is_deleted = False
        book.deleted_at = None
        return {"book_id": str(book.id), "is_deleted": book.is_deleted, "deleted_at": book.deleted_at}

    def get_history(
        self,
        *,
        book_id: UUID,
        source: str,
        state: str | None,
        start_date: datetime | None,
        end_date: datetime | None,
        page: int,
        limit: int,
    ) -> dict:
        if not self.repository.get_book(book_id):
            raise EntityDoesNotExistError("Libro no encontrado")

        records = self.repository.list_history(
            book_id=book_id,
            source=source,
            state=state,
            start_date=start_date,
            end_date=end_date,
        )
        total = len(records)
        start = (page - 1) * limit
        paginated = records[start : start + limit]

        output = []
        for record in paginated:
            store = self.repository.get_store(record.store_id)
            output.append(
                {
                    "price": record.price,
                    "state": record.state,
                    "checked_at": record.checked_at,
                    "domain": store.domain if store else "unknown",
                    "archived": record.archived,
                }
            )

        return {
            "book_id": str(book_id),
            "records": output,
            "meta": {
                "total": total,
                "page": page,
                "limit": limit,
                "pages": ceil(total / limit) if total else 0,
            },
        }

    def get_price_comparison(self, book_id: UUID) -> dict:
        if not self.repository.get_book(book_id):
            raise EntityDoesNotExistError("Libro no encontrado")

        offers = []
        for relation in self.repository.get_relations_for_book(book_id):
            if relation.status != "activo" or relation.current_price is None:
                continue
            store = self.repository.get_store(relation.store_id)
            offers.append(
                {
                    "domain": store.domain if store else "unknown",
                    "price": relation.current_price,
                    "status": relation.status,
                }
            )

        offers.sort(key=lambda item: item["price"])
        return {
            "book_id": str(book_id),
            "best_offer": offers[0] if offers else None,
            "offers": offers,
        }

    def create_archive_job(self, older_than_days: int, min_active_records_per_book: int) -> dict:
        if older_than_days <= 0:
            raise ValidationError("older_than_days debe ser mayor que 0")
        if min_active_records_per_book < 1:
            raise ValidationError("min_active_records_per_book debe ser mayor o igual a 1")

        job = self.repository.create_archive_job()
        job = self.repository.run_archive_job(job.id, older_than_days, min_active_records_per_book)
        return asdict(job)

    def get_archive_job(self, job_id: UUID) -> dict:
        job = self.repository.get_archive_job(job_id)
        if not job:
            raise EntityDoesNotExistError("Archive job no encontrado")
        return asdict(job)

    @staticmethod
    def _extract_book_identity(product_url: str) -> tuple[str, list[str], str | None]:
        parsed = urlparse(product_url)
        query = parse_qs(parsed.query)
        isbn = None

        if query.get("isbn"):
            isbn = query["isbn"][0]
        else:
            match = ISBN_PATTERN.search(product_url)
            if match:
                isbn = match.group(1)

        slug = parsed.path.strip("/").split("/")[-1] or "libro"
        title = slug.replace("-", " ").strip().title()
        if not title:
            title = "Libro sin título"
        return title, ["Autor desconocido"], isbn
