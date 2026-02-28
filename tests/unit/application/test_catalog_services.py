import pytest

from bsentinel.application.services import CatalogCommandService, CatalogQueryService
from bsentinel.exceptions import UnsupportedStoreError, ValidationError
from bsentinel.infrastructure.openlibrary import OpenLibraryClient
from bsentinel.infrastructure.persistence.in_memory import (
    InMemoryBookRepository,
    InMemoryRelationRepository,
    InMemoryStore,
    InMemoryStoreRepository,
)


@pytest.mark.asyncio
async def test_catalog_command_rejects_invalid_url():
    storage = InMemoryStore()
    service = CatalogCommandService(
        books=InMemoryBookRepository(storage),
        stores=InMemoryStoreRepository(storage),
        relations=InMemoryRelationRepository(storage),
        metadata=OpenLibraryClient(),
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
        metadata=OpenLibraryClient(),
    )

    with pytest.raises(UnsupportedStoreError):
        await service.create_book_from_url("https://example.com/books/123")


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
        metadata=OpenLibraryClient(),
    )
    query_service = CatalogQueryService(books=books, stores=stores, relations=relations)

    await command_service.create_book_from_url(
        "https://www.buscalibre.com.co/libro-clean-architecture-isbn-9780134494166"
    )

    listed = query_service.list_books(
        include_deleted=False,
        q="clean",
        isbn=None,
        author=None,
        category=None,
        page=1,
        limit=10,
    )

    assert listed["meta"]["total"] == 1
    assert listed["items"][0]["title"]
