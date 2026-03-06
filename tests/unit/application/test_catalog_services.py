import pytest

from bsentinel.application.services import CatalogCommandService, CatalogQueryService
from bsentinel.domain.models import ACTIVE
from bsentinel.exceptions import EntityAlreadyExistsError, UnsupportedStoreError, ValidationError
from bsentinel.infrastructure.persistence.in_memory import (
    InMemoryBookRepository,
    InMemoryRelationRepository,
    InMemoryStore,
    InMemoryStoreRepository,
)


class FakeMetadataProvider:
    async def enrich_by_isbn(self, isbn: str) -> dict:
        return {}


class FakeScraper:
    async def extract_book_details(self, store, product_url: str):
        if "missing-isbn" in product_url:
            return type("BookDetails", (), {"title": "Broken Book", "authors": ["Unknown"], "isbn": None})()
        return type(
            "BookDetails",
            (),
            {"title": "Clean Architecture", "authors": ["Robert C. Martin"], "isbn": "9780134494166"},
        )()

    async def scrape_book(self, store, product_url: str):
        return type("ScrapeResult", (), {"price": 99.9, "status": ACTIVE, "checked_at": None})()


@pytest.mark.asyncio
async def test_catalog_command_rejects_invalid_url():
    storage = InMemoryStore()
    service = CatalogCommandService(
        books=InMemoryBookRepository(storage),
        stores=InMemoryStoreRepository(storage),
        relations=InMemoryRelationRepository(storage),
        metadata=FakeMetadataProvider(),
        scraper=FakeScraper(),
    )

    with pytest.raises(ValidationError):
        await service.create_book_from_url("not-a-url")


@pytest.mark.asyncio
async def test_catalog_command_rejects_unsupported_domain():
    storage = InMemoryStore()
    service = CatalogCommandService(
        books=InMemoryBookRepository(storage),
        stores=InMemoryStoreRepository(storage),
        relations=InMemoryRelationRepository(storage),
        metadata=FakeMetadataProvider(),
        scraper=FakeScraper(),
    )

    with pytest.raises(UnsupportedStoreError):
        await service.create_book_from_url("https://example.com/books/123")


@pytest.mark.asyncio
async def test_catalog_command_rejects_missing_isbn():
    storage = InMemoryStore()
    service = CatalogCommandService(
        books=InMemoryBookRepository(storage),
        stores=InMemoryStoreRepository(storage),
        relations=InMemoryRelationRepository(storage),
        metadata=FakeMetadataProvider(),
        scraper=FakeScraper(),
    )

    with pytest.raises(ValidationError):
        await service.create_book_from_url("https://www.buscalibre.com.co/missing-isbn")


@pytest.mark.asyncio
async def test_catalog_command_reuses_existing_book_by_isbn_and_rejects_duplicate_relation():
    storage = InMemoryStore()
    books = InMemoryBookRepository(storage)
    relations = InMemoryRelationRepository(storage)
    stores = InMemoryStoreRepository(storage)
    service = CatalogCommandService(
        books=books,
        stores=stores,
        relations=relations,
        metadata=FakeMetadataProvider(),
        scraper=FakeScraper(),
    )

    book, _, _ = await service.create_book_from_url("https://www.buscalibre.com.co/libro-clean-architecture")

    with pytest.raises(EntityAlreadyExistsError):
        await service.create_book_from_url("https://www.buscalibre.com.co/libro-clean-architecture-duplicate")

    assert await books.get_by_isbn("9780134494166") is not None
    assert len(await relations.list_for_book(book.id)) == 1


@pytest.mark.asyncio
async def test_catalog_query_lists_created_books():
    storage = InMemoryStore()
    books = InMemoryBookRepository(storage)
    relations = InMemoryRelationRepository(storage)
    stores = InMemoryStoreRepository(storage)

    command_service = CatalogCommandService(
        books=books,
        stores=stores,
        relations=relations,
        metadata=FakeMetadataProvider(),
        scraper=FakeScraper(),
    )
    query_service = CatalogQueryService(books=books, stores=stores, relations=relations)

    await command_service.create_book_from_url("https://www.buscalibre.com.co/libro-clean-architecture")

    listed = await query_service.list_books(
        include_deleted=False,
        q="clean",
        isbn=None,
        author=None,
        category=None,
        page=1,
        limit=10,
    )

    assert listed["meta"]["total"] == 1
    assert listed["items"][0]["title"] == "Clean Architecture"
