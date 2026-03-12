"""Application external ports."""

from __future__ import annotations

from typing import Any, Protocol

from bsentinel.domain.models import Store


class BookDetailsPort(Protocol):
    title: str
    authors: list[str]
    isbn: str | None


class ScrapeResultPort(Protocol):
    price: float
    status: str
    checked_at: object


class ScraperPort(Protocol):
    async def extract_book_details(self, store: Store, product_url: str) -> BookDetailsPort: ...

    async def scrape_book(self, store: Store, product_url: str) -> ScrapeResultPort: ...


class MetadataProviderPort(Protocol):
    async def enrich_by_isbn(self, isbn: str) -> dict[str, Any]: ...
