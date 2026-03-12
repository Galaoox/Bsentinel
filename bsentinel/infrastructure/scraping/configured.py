"""Rule-driven scraper for configured stores."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from bsentinel.domain.models import ACTIVE, UNKNOWN, Store
from bsentinel.exceptions import ScrapingError

OUT_OF_STOCK = "agotado"
ISBN_PATTERN = re.compile(r"(97[89]\d{10}|\d{9}[\dXx])")
PRICE_PATTERN = re.compile(r"(?:\$|COP\$?|COP)?\s*([\d.]+(?:,\d{2})?|\d+(?:\.\d{3})*(?:,\d{2})?)")
logger = logging.getLogger(__name__)


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
    def __init__(self, browser_session: Any | None = None) -> None:
        self._session = browser_session

    def set_session(self, session: Any | None) -> None:
        self._session = session

    async def extract_book_details(self, store: Store, product_url: str) -> ExtractedBookDetails:
        page = await self._fetch_page(store, product_url)
        product = self._extract_product_json_ld(page)

        title, title_attempts = self._extract_text_field_with_attempts(store, "title", page, product)
        authors, author_attempts = self._extract_list_field_with_attempts(store, "authors", page, product)
        isbn, isbn_attempts = self._extract_text_field_with_attempts(store, "isbn", page, product)

        if not title:
            raise self._build_extraction_error(
                store=store,
                product_url=product_url,
                field_name="title",
                attempts=title_attempts,
                product=product,
            )
        if not authors:
            raise self._build_extraction_error(
                store=store,
                product_url=product_url,
                field_name="authors",
                attempts=author_attempts,
                product=product,
            )
        if not isbn:
            raise self._build_extraction_error(
                store=store,
                product_url=product_url,
                field_name="isbn",
                attempts=isbn_attempts,
                product=product,
            )

        return ExtractedBookDetails(title=title, authors=authors, isbn=isbn)

    async def scrape_book(self, store: Store, product_url: str) -> ScrapeResult:
        page = await self._fetch_page(store, product_url)
        product = self._extract_product_json_ld(page)
        checked_at = datetime.now(UTC)

        status = self._extract_text_field(store, "availability", page, product) or ACTIVE
        price_value = self._extract_text_field(store, "price", page, product)
        price = self._parse_price(price_value)

        if price is None:
            if status == OUT_OF_STOCK:
                price = 0.0
            else:
                status = UNKNOWN
                price = 0.0

        return ScrapeResult(price=price, status=status, checked_at=checked_at)

    async def _fetch_page(self, store: Store, product_url: str) -> Any:
        if self._session is None:
            raise ScrapingError(
                f"Scraping runtime is not initialized for store {store.domain}",
                reason="runtime_unavailable",
                diagnostics={"store_domain": store.domain, "product_url": product_url},
            )

        try:
            page = await self._session.fetch(product_url)
            self._validate_page_response(store, product_url, page)
            return page
        except Exception as exc:  # pragma: no cover - network/runtime behavior depends on target site
            if isinstance(exc, ScrapingError):
                raise
            raise ScrapingError(
                f"Unable to fetch page for store {store.domain}",
                reason="fetch_failed",
                diagnostics={
                    "store_domain": store.domain,
                    "product_url": product_url,
                    "error_type": type(exc).__name__,
                },
            ) from exc

    def _validate_page_response(self, store: Store, product_url: str, page: Any) -> None:
        body_bytes = self._read_body(page)
        body_text = body_bytes.decode(getattr(page, "encoding", "utf-8") or "utf-8", errors="ignore").strip()
        status_code = int(getattr(page, "status", 0) or 0)
        content_type = str((getattr(page, "headers", {}) or {}).get("content-type", "")).lower()

        if status_code >= 400:
            raise self._build_response_error(store, product_url, page, "http_error")
        if status_code == 202 and len(body_text) < 32:
            raise self._build_response_error(store, product_url, page, "accepted_without_html")
        if not body_text:
            raise self._build_response_error(store, product_url, page, "empty_body")
        if content_type and "html" not in content_type and "xhtml+xml" not in content_type:
            raise self._build_response_error(store, product_url, page, "unexpected_content_type")

    def _read_body(self, page: Any) -> bytes:
        body = getattr(page, "body", b"")
        if isinstance(body, bytes):
            return body
        if isinstance(body, str):
            return body.encode("utf-8")
        return bytes(body or b"")

    def _extract_product_json_ld(self, selector: Any) -> dict[str, Any]:
        for raw_script in selector.css("script[type='application/ld+json']::text").getall():
            for candidate in self._iter_json_objects(str(raw_script)):
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
        selector: Any,
        product: dict[str, Any],
    ) -> str | float | None:
        value, _ = self._extract_text_field_with_attempts(store, field_name, selector, product)
        return value

    def _extract_list_field(self, store: Store, field_name: str, selector: Any, product: dict[str, Any]) -> list[str]:
        values, _ = self._extract_list_field_with_attempts(store, field_name, selector, product)
        return values

    def _extract_text_field_with_attempts(
        self,
        store: Store,
        field_name: str,
        selector: Any,
        product: dict[str, Any],
    ) -> tuple[str | float | None, list[dict[str, Any]]]:
        field_rules = store.extraction_rules.get(field_name) or {}
        attempts: list[dict[str, Any]] = []
        for index, source in enumerate(field_rules.get("sources", []), start=1):
            values = self._extract_source_values(source, selector, product)
            attempt = self._build_attempt(field_name, index, source, values)
            for value in values:
                normalized = self._normalize_value(source.get("normalizer"), value)
                if normalized is None:
                    continue
                if isinstance(normalized, str) and normalized.strip():
                    attempt["usable_values"] = 1
                    self._log_source_attempt(store, field_name, attempt)
                    return normalized.strip(), attempts + [attempt]
                if isinstance(normalized, (int, float)):
                    attempt["usable_values"] = 1
                    self._log_source_attempt(store, field_name, attempt)
                    return float(normalized), attempts + [attempt]
            self._log_source_attempt(store, field_name, attempt)
            attempts.append(attempt)
        return None, attempts

    def _extract_list_field_with_attempts(
        self,
        store: Store,
        field_name: str,
        selector: Any,
        product: dict[str, Any],
    ) -> tuple[list[str], list[dict[str, Any]]]:
        field_rules = store.extraction_rules.get(field_name) or {}
        attempts: list[dict[str, Any]] = []
        for index, source in enumerate(field_rules.get("sources", []), start=1):
            values = self._extract_source_values(source, selector, product)
            attempt = self._build_attempt(field_name, index, source, values)
            normalized_values: list[str] = []
            for value in values:
                normalized = self._normalize_value(source.get("normalizer"), value)
                if isinstance(normalized, str) and normalized.strip():
                    normalized_values.append(normalized.strip())
            attempt["usable_values"] = len(normalized_values)
            self._log_source_attempt(store, field_name, attempt)
            if normalized_values:
                return normalized_values, attempts + [attempt]
            attempts.append(attempt)
        return [], attempts

    def _build_attempt(
        self,
        field_name: str,
        index: int,
        source: dict[str, Any],
        values: list[Any],
    ) -> dict[str, Any]:
        return {
            "field_name": field_name,
            "source_index": index,
            "source_kind": source.get("kind"),
            "selector": source.get("selector"),
            "path": source.get("path"),
            "attribute": source.get("attribute"),
            "normalizer": source.get("normalizer"),
            "match_count": len(values),
            "usable_values": 0,
        }

    def _log_source_attempt(self, store: Store, field_name: str, attempt: dict[str, Any]) -> None:
        logger.debug(
            "Scraping source evaluated",
            extra={
                "store_domain": store.domain,
                "field_name": field_name,
                "source_attempt": attempt,
            },
        )

    def _build_extraction_error(
        self,
        *,
        store: Store,
        product_url: str,
        field_name: str,
        attempts: list[dict[str, Any]],
        product: dict[str, Any],
    ) -> ScrapingError:
        diagnostics = {
            "store_domain": store.domain,
            "product_url": product_url,
            "field_name": field_name,
            "source_attempts": attempts,
            "product_json_ld_found": bool(product),
            "attempted_sources": len(attempts),
        }
        logger.warning(
            "Scraping field extraction failed",
            extra=diagnostics,
        )
        return ScrapingError(
            f"Unable to extract {field_name} from {store.domain} page",
            reason=f"{field_name}_not_found",
            diagnostics=diagnostics,
        )

    def _build_response_error(self, store: Store, product_url: str, page: Any, reason: str) -> ScrapingError:
        body_bytes = self._read_body(page)
        diagnostics = {
            "store_domain": store.domain,
            "product_url": product_url,
            "final_url": str(getattr(page, "url", product_url)),
            "status_code": getattr(page, "status", None),
            "content_type": (getattr(page, "headers", {}) or {}).get("content-type"),
            "body_length": len(body_bytes),
        }
        logger.warning(
            "Scraping HTTP response unusable",
            extra={"scraping_reason": reason, **diagnostics},
        )
        return ScrapingError(
            f"Unable to fetch usable HTML for store {store.domain}: {reason}",
            reason=reason,
            diagnostics=diagnostics,
        )

    def _extract_source_values(self, source: dict[str, Any], selector: Any, product: dict[str, Any]) -> list[Any]:
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

    def _extract_css_values(self, selector: Any, source: dict[str, Any]) -> list[str]:
        query = str(source.get("selector") or "").strip()
        attribute = str(source.get("attribute") or "").strip()
        if not query or not attribute:
            return []
        if attribute == "text":
            return [str(value) for value in selector.css(f"{query}::text").getall()]
        return [str(value) for value in selector.css(f"{query}::attr({attribute})").getall()]

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
