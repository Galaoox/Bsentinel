"""Buscalibre scraper and extractor."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
from scrapy import Selector

from bsentinel import settings
from bsentinel.domain.models import ACTIVE, UNKNOWN
from bsentinel.exceptions import ScrapingError

OUT_OF_STOCK = "agotado"
ISBN_PATTERN = re.compile(r"(97[89]\d{10}|\d{9}[\dXx])")
PRICE_PATTERN = re.compile(r"(?:\$|COP\$?|COP)?\s*([\d.]+(?:,\d{2})?|\d+(?:\.\d{3})*(?:,\d{2})?)")


@dataclass(slots=True)
class ExtractedBookDetails:
    title: str
    authors: list[str]
    isbn: str | None


@dataclass(slots=True)
class ScrapeResult:
    price: float
    status: str
    checked_at: datetime


class BuscalibreScraper:
    def __init__(self) -> None:
        self._headers = {"User-Agent": "Mozilla/5.0"}

    async def extract_book_details(self, product_url: str) -> ExtractedBookDetails:
        html = await self._fetch_html(product_url)
        product = self._extract_product_json_ld(html)

        title = self._extract_title(product, html)
        authors = self._extract_authors(product)
        isbn = self._extract_isbn(product, product_url, html)

        if not title:
            raise ScrapingError("Unable to extract title from Buscalibre page")

        return ExtractedBookDetails(
            title=title,
            authors=authors or ["Unknown Author"],
            isbn=isbn,
        )

    async def scrape_book(self, product_url: str) -> ScrapeResult:
        html = await self._fetch_html(product_url)
        product = self._extract_product_json_ld(html)
        checked_at = datetime.now(UTC)

        status = self._extract_status(product, html)
        price = self._extract_price(product, html)

        if price is None:
            if status == OUT_OF_STOCK:
                price = 0.0
            else:
                status = UNKNOWN
                price = 0.0

        return ScrapeResult(price=price, status=status, checked_at=checked_at)

    async def _fetch_html(self, product_url: str) -> str:
        try:
            async with httpx.AsyncClient(timeout=settings.scraping_timeout, follow_redirects=True) as client:
                response = await client.get(product_url, headers=self._headers)
                response.raise_for_status()
            return response.text
        except Exception as exc:  # pragma: no cover - network behavior depends on target site
            raise ScrapingError("Unable to fetch Buscalibre page") from exc

    def _extract_product_json_ld(self, html: str) -> dict[str, Any]:
        selector = Selector(text=html)
        for raw_script in selector.css("script[type='application/ld+json']::text").getall():
            for candidate in self._iter_json_objects(raw_script):
                if candidate.get("@type") == "Product":
                    return candidate
        return {}

    def _iter_json_objects(self, raw_script: str) -> list[dict[str, Any]]:
        try:
            parsed = json.loads(raw_script)
        except json.JSONDecodeError:
            return []

        queue: list[Any] = [parsed]
        items: list[dict[str, Any]] = []
        while queue:
            current = queue.pop(0)
            if isinstance(current, dict):
                items.append(current)
                queue.extend(current.values())
            elif isinstance(current, list):
                queue.extend(current)
        return items

    def _extract_title(self, product: dict[str, Any], html: str) -> str:
        if isinstance(product.get("name"), str) and product["name"].strip():
            return product["name"].strip()

        selector = Selector(text=html)
        title = selector.css("h1::text").get()
        if title:
            return title.split(" - ")[0].strip()

        og_title = selector.css("meta[property='og:title']::attr(content)").get()
        if og_title:
            cleaned = og_title.replace("- Buscalibre Colombia", "").replace("Libro ", "", 1)
            return cleaned.strip()
        return ""

    def _extract_authors(self, product: dict[str, Any]) -> list[str]:
        raw = product.get("author")
        if isinstance(raw, dict):
            name = raw.get("name")
            return [name.strip()] if isinstance(name, str) and name.strip() else []
        if isinstance(raw, list):
            authors = []
            for item in raw:
                if isinstance(item, dict) and isinstance(item.get("name"), str) and item["name"].strip():
                    authors.append(item["name"].strip())
                elif isinstance(item, str) and item.strip():
                    authors.append(item.strip())
            return authors
        if isinstance(raw, str) and raw.strip():
            return [raw.strip()]
        return []

    def _extract_isbn(self, product: dict[str, Any], product_url: str, html: str) -> str | None:
        if isinstance(product.get("isbn"), str) and product["isbn"].strip():
            return product["isbn"].strip()

        for source in (product_url, html):
            match = ISBN_PATTERN.search(source)
            if match:
                return match.group(1)
        return None

    def _extract_status(self, product: dict[str, Any], html: str) -> str:
        offers = product.get("offers") or []
        if isinstance(offers, dict):
            offers = [offers]
        for offer in offers:
            availability = str(offer.get("availability") or "").lower()
            if "outofstock" in availability:
                return OUT_OF_STOCK
            if any(token in availability for token in ("instock", "preorder", "limitedavailability")):
                return ACTIVE

        html_lower = html.lower()
        if "agotado" in html_lower or "no disponible" in html_lower:
            return OUT_OF_STOCK
        return ACTIVE

    def _extract_price(self, product: dict[str, Any], html: str) -> float | None:
        offers = product.get("offers") or []
        if isinstance(offers, dict):
            offers = [offers]
        for offer in offers:
            raw_price = offer.get("price") or offer.get("lowPrice") or offer.get("highPrice")
            parsed = self._parse_price(raw_price)
            if parsed is not None:
                return parsed

        selector = Selector(text=html)
        candidates = []
        for query in (
            "meta[property='product:price:amount']::attr(content)",
            "meta[itemprop='price']::attr(content)",
            "[itemprop='price']::attr(content)",
            ".precio-ahora::text",
            ".precioAhora::text",
            ".precio::text",
            ".sale-price::text",
        ):
            candidates.extend(selector.css(query).getall())

        for candidate in candidates:
            parsed = self._parse_price(candidate)
            if parsed is not None:
                return parsed
        return None

    def _parse_price(self, raw_price: Any) -> float | None:
        if raw_price is None:
            return None
        if isinstance(raw_price, (int, float)):
            return round(float(raw_price), 2)

        text = str(raw_price).strip()
        if not text:
            return None

        match = PRICE_PATTERN.search(text)
        if not match:
            return None

        cleaned = match.group(1).replace(".", "").replace(",", ".")
        try:
            return round(float(cleaned), 2)
        except ValueError:
            return None
