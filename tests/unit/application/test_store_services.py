from uuid import UUID

import pytest

from bsentinel.application.services.stores import StoreCommandService, StoreQueryService
from bsentinel.exceptions import EntityDoesNotExistError, ValidationError
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


@pytest.mark.asyncio
async def test_delete_store_soft_deletes_active_store():
    repository = InMemoryStoreRepository(InMemoryStore())
    service = StoreCommandService(stores=repository)
    created = await service.create_store(
        name="Delete Me",
        domain="www.delete-me.com",
        country_code="CO",
        scrape_interval_hours=6,
        is_active=True,
        extraction_rules=build_default_buscalibre_rules(),
    )

    store_id = UUID(created["id"])

    await service.delete_store(store_id)

    deleted_store = await repository.get(store_id)
    active_stores = await repository.list()

    assert deleted_store is not None
    assert deleted_store.is_deleted is True
    assert deleted_store.deleted_at is not None
    assert all(store.id != store_id for store in active_stores)


@pytest.mark.asyncio
async def test_delete_store_is_idempotent_for_deleted_store():
    repository = InMemoryStoreRepository(InMemoryStore())
    service = StoreCommandService(stores=repository)
    created = await service.create_store(
        name="Delete Twice",
        domain="www.delete-twice.com",
        country_code="CO",
        scrape_interval_hours=6,
        is_active=True,
        extraction_rules=build_default_buscalibre_rules(),
    )

    store_id = UUID(created["id"])

    await service.delete_store(store_id)
    deleted_store = await repository.get(store_id)
    first_deleted_at = deleted_store.deleted_at if deleted_store is not None else None

    await service.delete_store(store_id)

    deleted_store_again = await repository.get(store_id)

    assert deleted_store_again is not None
    assert deleted_store_again.is_deleted is True
    assert deleted_store_again.deleted_at == first_deleted_at


@pytest.mark.asyncio
async def test_delete_store_raises_when_store_does_not_exist():
    service = StoreCommandService(stores=InMemoryStoreRepository(InMemoryStore()))

    with pytest.raises(EntityDoesNotExistError):
        await service.delete_store(UUID("f2ad5f24-8a16-45db-af8a-66c359e5f3e9"))


@pytest.mark.asyncio
async def test_restore_store_reactivates_deleted_store_and_returns_payload():
    repository = InMemoryStoreRepository(InMemoryStore())
    service = StoreCommandService(stores=repository)
    created = await service.create_store(
        name="Restore Me",
        domain="www.restore-me.com",
        country_code="CO",
        scrape_interval_hours=6,
        is_active=True,
        extraction_rules=build_default_buscalibre_rules(),
    )
    store_id = UUID(created["id"])

    await service.delete_store(store_id)

    restored = await service.restore_store(store_id)

    restored_store = await repository.get(store_id)
    active_stores = await repository.list()

    assert restored["id"] == str(store_id)
    assert restored["domain"] == "www.restore-me.com"
    assert restored_store is not None
    assert restored_store.is_deleted is False
    assert restored_store.deleted_at is None
    assert any(store.id == store_id for store in active_stores)


@pytest.mark.asyncio
async def test_restore_store_is_idempotent_for_active_store():
    repository = InMemoryStoreRepository(InMemoryStore())
    service = StoreCommandService(stores=repository)
    created = await service.create_store(
        name="Restore Twice",
        domain="www.restore-twice.com",
        country_code="CO",
        scrape_interval_hours=6,
        is_active=True,
        extraction_rules=build_default_buscalibre_rules(),
    )

    store_id = UUID(created["id"])

    restored = await service.restore_store(store_id)

    active_store = await repository.get(store_id)

    assert restored["id"] == str(store_id)
    assert active_store is not None
    assert active_store.is_deleted is False
    assert active_store.deleted_at is None


@pytest.mark.asyncio
async def test_restore_store_raises_when_store_does_not_exist():
    service = StoreCommandService(stores=InMemoryStoreRepository(InMemoryStore()))

    with pytest.raises(EntityDoesNotExistError):
        await service.restore_store(UUID("01f78f21-e3f5-4c8b-9397-c83ebeb8632e"))
