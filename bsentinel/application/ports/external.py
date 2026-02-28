"""Application external ports."""

from __future__ import annotations

from typing import Any, Protocol


class ScrapeResultPort(Protocol):
    price: float
    status: str
    checked_at: object


class ScraperPort(Protocol):
    async def scrape_book(self, product_url: str) -> ScrapeResultPort: ...


class MetadataProviderPort(Protocol):
    async def enrich_by_isbn(self, isbn: str) -> dict[str, Any]: ...
