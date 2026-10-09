"""Application external ports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from bsentinel.domain.models import Store


class BookDetailsPort(Protocol):
    title: str
    authors: list[str]
    isbn: str | None


class ScrapeResultPort(Protocol):
    price: float
    status: str
    checked_at: datetime


@dataclass(frozen=True, slots=True)
class ProductExtraction:
    """Operation-local values extracted from one usable response; no HTML retained."""

    details: BookDetailsPort
    result: ScrapeResultPort


class ScraperPort(Protocol):
    async def extract_product(self, store: Store, product_url: str) -> ProductExtraction: ...

    async def extract_book_details(self, store: Store, product_url: str) -> BookDetailsPort: ...

    async def scrape_book(self, store: Store, product_url: str) -> ScrapeResultPort: ...


class MetadataProviderPort(Protocol):
    async def enrich_by_isbn(self, isbn: str) -> dict[str, Any]: ...
