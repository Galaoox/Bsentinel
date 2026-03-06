"""Rule-driven scraper for configured stores."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
from scrapy import Selector

from bsentinel import settings
from bsentinel.domain.models import ACTIVE, UNKNOWN, Store
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


class ConfiguredStoreScraper:
    def __init__(self) -> None:
        self._headers = {"User-Agent": "Mozilla/5.0"}

    async def extract_book_details(self, store: Store, product_url: str) -> ExtractedBookDetails:
        html = await self._fetch_html(store, product_url)
        selector = Selector(text=html)
        product = self._extract_product_json_ld(selector)

        title = self._extract_text_field(store, "title", selector, product)
        authors = self._extract_list_field(store, "authors", selector, product)
        isbn = self._extract_text_field(store, "isbn", selector, product)

        if not title:
            raise ScrapingError(f"Unable to extract title from {store.domain} page")
        if not authors:
            raise ScrapingError(f"Unable to extract authors from {store.domain} page")

        return ExtractedBookDetails(title=title, authors=authors, isbn=isbn)

    async def scrape_book(self, store: Store, product_url: str) -> ScrapeResult:
        html = await self._fetch_html(store, product_url)
        selector = Selector(text=html)
        product = self._extract_product_json_ld(selector)
        checked_at = datetime.now(UTC)

        status = self._extract_text_field(store, "availability", selector, product) or ACTIVE
        price_value = self._extract_text_field(store, "price", selector, product)
        price = self._parse_price(price_value)

        if price is None:
            if status == OUT_OF_STOCK:
                price = 0.0
            else:
                status = UNKNOWN
                price = 0.0

        return ScrapeResult(price=price, status=status, checked_at=checked_at)

    async def _fetch_html(self, store: Store, product_url: str) -> str:
        try:
            async with httpx.AsyncClient(timeout=settings.scraping_timeout, follow_redirects=True) as client:
                response = await client.get(product_url, headers=self._headers)
                response.raise_for_status()
            return response.text
        except Exception as exc:  # pragma: no cover - network behavior depends on target site
            raise ScrapingError(f"Unable to fetch page for store {store.domain}") from exc

    def _extract_product_json_ld(self, selector: Selector) -> dict[str, Any]:
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

    def _extract_text_field(
        self,
        store: Store,
        field_name: str,
        selector: Selector,
        product: dict[str, Any],
    ) -> str | float | None:
        field_rules = store.extraction_rules.get(field_name) or {}
        for source in field_rules.get("sources", []):
            values = self._extract_source_values(source, selector, product)
            for value in values:
                normalized = self._normalize_value(source.get("normalizer"), value)
                if normalized is None:
                    continue
                if isinstance(normalized, str) and normalized.strip():
                    return normalized.strip()
                if isinstance(normalized, (int, float)):
                    return float(normalized)
        return None

    def _extract_list_field(self, store: Store, field_name: str, selector: Selector, product: dict[str, Any]) -> list[str]:
        field_rules = store.extraction_rules.get(field_name) or {}
        for source in field_rules.get("sources", []):
            values = self._extract_source_values(source, selector, product)
            normalized_values: list[str] = []
            for value in values:
                normalized = self._normalize_value(source.get("normalizer"), value)
                if isinstance(normalized, str) and normalized.strip():
                    normalized_values.append(normalized.strip())
            if normalized_values:
                return normalized_values
        return []

    def _extract_source_values(self, source: dict[str, Any], selector: Selector, product: dict[str, Any]) -> list[Any]:
        kind = source.get("kind")
        raw_values: list[Any] = []
        if kind == "css":
            raw_values = self._extract_css_values(selector, source)
        elif kind == "json_ld":
            raw_values = self._extract_json_ld_values(product, str(source.get("path") or ""))

        regex = source.get("regex")
        if not regex:
            return raw_values

        pattern = re.compile(regex)
        matched: list[str] = []
        for value in raw_values:
            match = pattern.search(str(value))
            if match:
                matched.append(match.group(1) if match.groups() else match.group(0))
        return matched

    def _extract_css_values(self, selector: Selector, source: dict[str, Any]) -> list[str]:
        query = str(source.get("selector") or "").strip()
        attribute = str(source.get("attribute") or "").strip()
        if not query or not attribute:
            return []
        if attribute == "text":
            return selector.css(f"{query}::text").getall()
        return selector.css(f"{query}::attr({attribute})").getall()

    def _extract_json_ld_values(self, product: dict[str, Any], path: str) -> list[Any]:
        if not path:
            return []

        current: list[Any] = [product]
        for segment in path.split("."):
            expand_list = segment.endswith("[]")
            key = segment[:-2] if expand_list else segment
            next_values: list[Any] = []
            for item in current:
                if isinstance(item, dict) and key in item:
                    value = item[key]
                    if expand_list and isinstance(value, list):
                        next_values.extend(value)
                    elif expand_list:
                        next_values.append(value)
                    else:
                        next_values.append(value)
                elif expand_list and isinstance(item, list):
                    next_values.extend(item)
            current = next_values
            if not current:
                break

        flattened: list[Any] = []
        for item in current:
            if isinstance(item, list):
                flattened.extend(item)
            else:
                flattened.append(item)
        return flattened

    def _normalize_value(self, normalizer: str | None, value: Any) -> str | float | None:
        if value is None:
            return None
        if normalizer in {None, "text_trim"}:
            text = str(value).strip()
            return text or None
        if normalizer == "isbn_digits":
            match = ISBN_PATTERN.search(str(value))
            return match.group(1).upper() if match else None
        if normalizer == "price_latam":
            parsed = self._parse_price(value)
            return parsed
        if normalizer == "availability_buscalibre":
            text = str(value).strip().lower()
            if not text:
                return None
            if "outofstock" in text or "agotado" in text or "no disponible" in text:
                return OUT_OF_STOCK
            if any(token in text for token in ("instock", "preorder", "limitedavailability", "disponible")):
                return ACTIVE
            return UNKNOWN
        return str(value).strip() or None

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
