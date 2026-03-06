"""Store administration application services."""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Any
from uuid import UUID

from scrapy import Selector

from bsentinel.application.ports import StoreRepositoryPort
from bsentinel.domain.models import Store
from bsentinel.exceptions import EntityAlreadyExistsError, EntityDoesNotExistError, ValidationError

ALPHA2_PATTERN = re.compile(r"^[A-Z]{2}$")
SUPPORTED_SOURCE_KINDS = {"css", "json_ld"}
SUPPORTED_NORMALIZERS = {"text_trim", "isbn_digits", "price_latam", "availability_buscalibre"}
REQUIRED_RULE_FIELDS = {"title", "authors", "isbn", "price"}
OPTIONAL_RULE_FIELDS = {"availability"}


class StoreCommandService:
    def __init__(self, *, stores: StoreRepositoryPort) -> None:
        self.stores = stores

    async def create_store(
        self,
        *,
        name: str,
        domain: str,
        country_code: str,
        scrape_interval_hours: int,
        is_active: bool,
        extraction_rules: dict[str, Any],
    ) -> dict:
        normalized_domain = self._normalize_domain(domain)
        if await self.stores.get_by_domain(normalized_domain):
            raise EntityAlreadyExistsError("Store already exists")

        store = Store(
            name=name.strip(),
            domain=normalized_domain,
            country_code=self._normalize_country_code(country_code),
            scrape_interval_hours=scrape_interval_hours,
            is_active=is_active,
            extraction_rules=self._validate_rules(extraction_rules),
        )
        await self.stores.add(store)
        return self._detail_payload(store)

    async def update_store(
        self,
        store_id: UUID,
        *,
        name: str,
        domain: str,
        country_code: str,
        scrape_interval_hours: int,
        is_active: bool,
        extraction_rules: dict[str, Any],
    ) -> dict:
        store = await self.stores.get(store_id)
        if not store or store.is_deleted:
            raise EntityDoesNotExistError("Store not found")

        normalized_domain = self._normalize_domain(domain)
        duplicate = await self.stores.get_by_domain(normalized_domain)
        if duplicate and duplicate.id != store.id:
            raise EntityAlreadyExistsError("Store already exists")

        updated = replace(
            store,
            name=name.strip(),
            domain=normalized_domain,
            country_code=self._normalize_country_code(country_code),
            scrape_interval_hours=scrape_interval_hours,
            is_active=is_active,
            extraction_rules=self._validate_rules(extraction_rules),
        )
        await self.stores.save(updated)
        return self._detail_payload(updated)

    async def patch_store(
        self,
        store_id: UUID,
        *,
        is_active: bool | None,
        scrape_interval_hours: int | None,
    ) -> dict:
        store = await self.stores.get(store_id)
        if not store or store.is_deleted:
            raise EntityDoesNotExistError("Store not found")

        updated = replace(
            store,
            is_active=store.is_active if is_active is None else is_active,
            scrape_interval_hours=store.scrape_interval_hours if scrape_interval_hours is None else scrape_interval_hours,
        )
        if updated.scrape_interval_hours < 1:
            raise ValidationError("scrape_interval_hours must be greater than or equal to 1")

        await self.stores.save(updated)
        return self._detail_payload(updated)

    def _normalize_domain(self, domain: str) -> str:
        normalized = domain.strip().lower()
        if not normalized:
            raise ValidationError("domain is required")
        return normalized

    def _normalize_country_code(self, country_code: str) -> str:
        normalized = country_code.strip().upper()
        if not ALPHA2_PATTERN.fullmatch(normalized):
            raise ValidationError("country_code must be a valid ISO alpha-2 code")
        return normalized

    def _validate_rules(self, extraction_rules: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(extraction_rules, dict):
            raise ValidationError("extraction_rules must be an object")

        missing_fields = sorted(REQUIRED_RULE_FIELDS.difference(extraction_rules))
        if missing_fields:
            raise ValidationError(f"Missing required extraction fields: {', '.join(missing_fields)}")

        allowed_fields = REQUIRED_RULE_FIELDS | OPTIONAL_RULE_FIELDS
        unexpected_fields = sorted(set(extraction_rules).difference(allowed_fields))
        if unexpected_fields:
            raise ValidationError(f"Unsupported extraction fields: {', '.join(unexpected_fields)}")

        validated: dict[str, Any] = {}
        for field_name, field_rules in extraction_rules.items():
            if not isinstance(field_rules, dict):
                raise ValidationError(f"Field '{field_name}' must be an object")
            sources = field_rules.get("sources")
            if not isinstance(sources, list) or not sources:
                raise ValidationError(f"Field '{field_name}' must define at least one source")
            validated[field_name] = {"sources": [self._validate_source(field_name, source) for source in sources]}
        return validated

    def _validate_source(self, field_name: str, source: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(source, dict):
            raise ValidationError(f"Sources for '{field_name}' must be objects")

        kind = str(source.get("kind") or "").strip()
        if kind not in SUPPORTED_SOURCE_KINDS:
            raise ValidationError(f"Field '{field_name}' uses unsupported source kind '{kind}'")

        normalizer = source.get("normalizer")
        if normalizer is not None and normalizer not in SUPPORTED_NORMALIZERS:
            raise ValidationError(f"Field '{field_name}' uses unsupported normalizer '{normalizer}'")

        regex = source.get("regex")
        if regex is not None:
            try:
                re.compile(str(regex))
            except re.error as exc:
                raise ValidationError(f"Field '{field_name}' has an invalid regex") from exc

        if kind == "css":
            selector = str(source.get("selector") or "").strip()
            attribute = str(source.get("attribute") or "").strip()
            if not selector or not attribute:
                raise ValidationError(f"Field '{field_name}' css source requires selector and attribute")
            self._validate_css_selector(selector, field_name)
            return {
                "kind": "css",
                "selector": selector,
                "attribute": attribute,
                **({"regex": str(regex)} if regex is not None else {}),
                **({"normalizer": normalizer} if normalizer is not None else {}),
            }

        path = str(source.get("path") or "").strip()
        if not path:
            raise ValidationError(f"Field '{field_name}' json_ld source requires path")
        return {
            "kind": "json_ld",
            "path": path,
            **({"regex": str(regex)} if regex is not None else {}),
            **({"normalizer": normalizer} if normalizer is not None else {}),
        }

    def _validate_css_selector(self, selector: str, field_name: str) -> None:
        try:
            Selector(text="<html></html>").css(selector).getall()
        except Exception as exc:  # pragma: no cover - library exception type may vary
            raise ValidationError(f"Field '{field_name}' has an invalid CSS selector") from exc

    def _detail_payload(self, store: Store) -> dict:
        return {
            "id": str(store.id),
            "name": store.name,
            "domain": store.domain,
            "country_code": store.country_code,
            "scrape_interval_hours": store.scrape_interval_hours,
            "is_active": store.is_active,
            "extraction_rules": store.extraction_rules,
        }


class StoreQueryService:
    def __init__(self, *, stores: StoreRepositoryPort) -> None:
        self.stores = stores

    async def list_stores(self) -> dict:
        items = []
        for store in await self.stores.list():
            items.append(
                {
                    "id": str(store.id),
                    "name": store.name,
                    "domain": store.domain,
                    "country_code": store.country_code,
                    "scrape_interval_hours": store.scrape_interval_hours,
                    "is_active": store.is_active,
                }
            )
        return {"items": items, "meta": {"total": len(items)}}

    async def get_store(self, store_id: UUID) -> dict:
        store = await self.stores.get(store_id)
        if not store or store.is_deleted:
            raise EntityDoesNotExistError("Store not found")
        return {
            "id": str(store.id),
            "name": store.name,
            "domain": store.domain,
            "country_code": store.country_code,
            "scrape_interval_hours": store.scrape_interval_hours,
            "is_active": store.is_active,
            "extraction_rules": store.extraction_rules,
        }
