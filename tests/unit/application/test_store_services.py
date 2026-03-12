import pytest

from bsentinel.application.services.stores import StoreCommandService, StoreQueryService
from bsentinel.exceptions import ValidationError
from bsentinel.infrastructure.persistence.in_memory import InMemoryStore, InMemoryStoreRepository
from bsentinel.infrastructure.scraping.rules import build_default_buscalibre_rules


@pytest.mark.asyncio
async def test_create_store_rejects_invalid_country_code():
    service = StoreCommandService(stores=InMemoryStoreRepository(InMemoryStore()))

    with pytest.raises(ValidationError):
        await service.create_store(
            name="Test Store",
            domain="www.test.com",
            country_code="COL",
            scrape_interval_hours=6,
            is_active=True,
            extraction_rules=build_default_buscalibre_rules(),
        )


@pytest.mark.asyncio
async def test_create_store_rejects_invalid_selector():
    service = StoreCommandService(stores=InMemoryStoreRepository(InMemoryStore()))
    rules = build_default_buscalibre_rules()
    rules["title"]["sources"][0] = {"kind": "css", "selector": "div[", "attribute": "text"}

    with pytest.raises(ValidationError):
        await service.create_store(
            name="Test Store",
            domain="www.test.com",
            country_code="CO",
            scrape_interval_hours=6,
            is_active=True,
            extraction_rules=rules,
        )


@pytest.mark.asyncio
async def test_create_and_list_store():
    repository = InMemoryStoreRepository(InMemoryStore())
    command_service = StoreCommandService(stores=repository)
    query_service = StoreQueryService(stores=repository)

    created = await command_service.create_store(
        name="Libreria Demo",
        domain="www.demo.com",
        country_code="CO",
        scrape_interval_hours=8,
        is_active=True,
        extraction_rules=build_default_buscalibre_rules(),
    )
    listed = await query_service.list_stores()

    assert created["domain"] == "www.demo.com"
    assert listed["meta"]["total"] == 2
    assert any(item["domain"] == "www.demo.com" for item in listed["items"])


@pytest.mark.asyncio
async def test_create_store_accepts_explicit_price_normalizers():
    service = StoreCommandService(stores=InMemoryStoreRepository(InMemoryStore()))
    rules = build_default_buscalibre_rules()
    rules["price"]["sources"][0]["normalizer"] = "price_cop_mixed"
    rules["price"]["sources"][1]["normalizer"] = "price_cop"
    rules["price"]["sources"][2]["normalizer"] = "price_decimal"

    created = await service.create_store(
        name="Test Store",
        domain="www.test.com",
        country_code="CO",
        scrape_interval_hours=6,
        is_active=True,
        extraction_rules=rules,
    )

    assert created["extraction_rules"]["price"]["sources"][0]["normalizer"] == "price_cop_mixed"


@pytest.mark.asyncio
async def test_create_store_rejects_unknown_price_normalizer():
    service = StoreCommandService(stores=InMemoryStoreRepository(InMemoryStore()))
    rules = build_default_buscalibre_rules()
    rules["price"]["sources"][0]["normalizer"] = "price_unknown"

    with pytest.raises(ValidationError):
        await service.create_store(
            name="Test Store",
            domain="www.test.com",
            country_code="CO",
            scrape_interval_hours=6,
            is_active=True,
            extraction_rules=rules,
        )
