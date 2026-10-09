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
    async def extract_product(self, store, product_url: str):
        from datetime import UTC, datetime

        from bsentinel.application.ports.external import ProductExtraction
        result = await self.scrape_book(store, product_url)
        result.checked_at = datetime.now(UTC)
        return ProductExtraction(await self.extract_book_details(store, product_url), result)

    def __init__(self) -> None:
        self.calls = 0
        self.urls = []

    async def extract_book_details(self, store, product_url: str):
        self.calls += 1
        self.urls.append(product_url)
        if "missing-isbn" in product_url:
            return type("BookDetails", (), {"title": "Broken Book", "authors": ["Unknown"], "isbn": None})()
        return type(
            "BookDetails",
            (),
            {"title": "Clean Architecture", "authors": ["Robert C. Martin"], "isbn": "9780134494166"},
        )()

    async def scrape_book(self, store, product_url: str):
        return type("ScrapeResult", (), {"price": 99.9, "status": ACTIVE, "checked_at": None})()


class UnexpectedLookupStoreRepository:
    async def get_by_domain(self, domain: str):
        raise AssertionError(f"store lookup should not happen for unsupported domain: {domain}")


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
        stores=UnexpectedLookupStoreRepository(),
        relations=InMemoryRelationRepository(storage),
        metadata=FakeMetadataProvider(),
        scraper=FakeScraper(),
    )

    with pytest.raises(UnsupportedStoreError):
        await service.create_book_from_url("https://example.com/books/123")


@pytest.mark.asyncio
async def test_catalog_command_rejects_inactive_buscalibre_store_without_scraping():
    storage = InMemoryStore()
    scraper = FakeScraper()
    stores = InMemoryStoreRepository(storage)
    seeded_store = next(iter(storage.stores.values()))
    seeded_store.is_active = False
    service = CatalogCommandService(
        books=InMemoryBookRepository(storage),
        stores=stores,
        relations=InMemoryRelationRepository(storage),
        metadata=FakeMetadataProvider(),
        scraper=scraper,
    )

    with pytest.raises(UnsupportedStoreError):
        await service.create_book_from_url("https://www.buscalibre.com.co/books/123")

    assert scraper.calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("alias", "canonical"),
    [
        ("buscalibre.com.co", "www.buscalibre.com.co"),
        ("panamericana.com.co", "www.panamericana.com.co"),
    ],
)
async def test_catalog_command_resolves_store_alias_and_preserves_url_components(alias, canonical):
    storage = InMemoryStore()
    scraper = FakeScraper()
    books = InMemoryBookRepository(storage)
    relations = InMemoryRelationRepository(storage)
    stores = InMemoryStoreRepository(storage)
    service = CatalogCommandService(
        books=books,
        stores=stores,
        relations=relations,
        metadata=FakeMetadataProvider(),
        scraper=scraper,
    )

    original_url = f"https://{alias}/libro/isbn-123?ref=affiliate%2Fid&isbn=9780134494166#details"
    book, relation, site, _ = await service.create_book_from_url(original_url)

    expected_url = f"https://{canonical}/libro/isbn-123?ref=affiliate%2Fid&isbn=9780134494166#details"
    assert site == canonical
    assert scraper.urls == [expected_url]
    assert relation.product_url == expected_url
    assert relation.store_id == (await stores.get_by_domain(canonical)).id
    assert book.isbn == "9780134494166"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "https://buscalibre.com.co.evil.example/book",
        "https://evilbuscalibre.com.co/book",
        "https://shop.buscalibre.com.co/book",
        "https://user:pass@buscalibre.com.co/book",
        "https://buscalibre.com.co:443/book",
        "https://[buscalibre.com.co/book",
        "ftp://buscalibre.com.co/book",
    ],
)
async def test_catalog_command_rejects_unsafe_store_aliases_without_scraping(url):
    storage = InMemoryStore()
    scraper = FakeScraper()
    service = CatalogCommandService(
        books=InMemoryBookRepository(storage),
        stores=InMemoryStoreRepository(storage),
        relations=InMemoryRelationRepository(storage),
        metadata=FakeMetadataProvider(),
        scraper=scraper,
    )

    with pytest.raises((ValidationError, UnsupportedStoreError)):
        await service.create_book_from_url(url)

    assert scraper.calls == 0


@pytest.mark.asyncio
async def test_catalog_command_keeps_seed_store_relation_for_buscalibre_books():
    storage = InMemoryStore()
    scraper = FakeScraper()
    books = InMemoryBookRepository(storage)
    relations = InMemoryRelationRepository(storage)
    stores = InMemoryStoreRepository(storage)
    seeded_store = next(iter(storage.stores.values()))
    service = CatalogCommandService(
        books=books,
        stores=stores,
        relations=relations,
        metadata=FakeMetadataProvider(),
        scraper=scraper,
    )

    book, relation, site, _ = await service.create_book_from_url(
        "https://www.buscalibre.com.co/libro-clean-architecture"
    )

    assert site == "www.buscalibre.com.co"
    assert relation.book_id == book.id
    assert relation.store_id == seeded_store.id
    assert len(await relations.list_for_book(book.id)) == 1


@pytest.mark.asyncio
async def test_catalog_command_links_same_isbn_to_panamericana_without_duplicate_book():
    storage = InMemoryStore()
    scraper = FakeScraper()
    books = InMemoryBookRepository(storage)
    relations = InMemoryRelationRepository(storage)
    service = CatalogCommandService(
        books=books,
        stores=InMemoryStoreRepository(storage),
        relations=relations,
        metadata=FakeMetadataProvider(),
        scraper=scraper,
    )

    buscalibre_book, _, _, _ = await service.create_book_from_url(
        "https://www.buscalibre.com.co/libro-clean-architecture"
    )
    panamericana_book, relation, site, _ = await service.create_book_from_url(
        "https://www.panamericana.com.co/clean-architecture/p"
    )

    assert site == "www.panamericana.com.co"
    assert panamericana_book.id == buscalibre_book.id
    assert len(await books.list(include_deleted=True)) == 1
    assert len(await relations.list_for_book(buscalibre_book.id)) == 2
    panamericana_store = await InMemoryStoreRepository(storage).get_by_domain(site)
    assert panamericana_store is not None
    assert relation.store_id == panamericana_store.id


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

    book, _, _, _ = await service.create_book_from_url("https://www.buscalibre.com.co/libro-clean-architecture")

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
