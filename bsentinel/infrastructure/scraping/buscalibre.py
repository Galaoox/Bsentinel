"""Scraper simulado para Buscalibre (MVP local)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime

from bsentinel.domain.models import ACTIVE


@dataclass(slots=True)
class ScrapeResult:
    price: float
    status: str
    checked_at: datetime


class BuscalibreScraper:
    async def scrape_book(self, product_url: str) -> ScrapeResult:
        digest = hashlib.sha256(product_url.encode("utf-8")).hexdigest()
        cents = int(digest[:8], 16) % 9_000_00
        price = round((cents + 10_000) / 100, 2)
        return ScrapeResult(price=price, status=ACTIVE, checked_at=datetime.now(UTC))
