from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from bsentinel.application.services.catalog import CatalogCommandService
from bsentinel.application.services.catalog_bulk import CatalogBulkService
from bsentinel.application.services.pricing import ScrapingService
from bsentinel.exceptions import BulkItemError, ScrapingError
from bsentinel.infrastructure.persistence.in_memory import (
    InMemoryBookRepository,
    InMemoryHistoryRepository,
    InMemoryRelationRepository,
    InMemoryStore,
    InMemoryStoreRepository,
)
from bsentinel.infrastructure.persistence.in_memory.transactions import InMemoryCatalogTransaction

URL = 'https://www.buscalibre.com.co/book-isbn-1'


class Scraper:
    async def extract_book_details(self, store, url):
        return SimpleNamespace(title=url, authors=['Fixture Author'], isbn=url.split('isbn-')[1])

    async def scrape_book(self, store, url):
        return SimpleNamespace(price=42.5, status='activo', checked_at=datetime.now(UTC))


class Metadata:
    async def enrich_by_isbn(self, isbn):
        return {'publisher': 'Fixture Publisher'}


def service(store, metadata=None, scraper=None):
    tx = InMemoryCatalogTransaction(store)
    books = InMemoryBookRepository(tx.working)
    stores = InMemoryStoreRepository(tx.working)
    relations = InMemoryRelationRepository(tx.working)
    history = InMemoryHistoryRepository(tx.working)
    scraper = scraper or Scraper()
    command = CatalogCommandService(books=books, stores=stores, relations=relations,
                                    metadata=metadata or Metadata(), scraper=scraper)
    scraping = ScrapingService(books=books, stores=stores, relations=relations,
                              history=history, scraper=scraper)
    return CatalogBulkService(command, scraping, tx)


async def test_bulk_service_orders_items_and_reuses_isbn():
    store = InMemoryStore()
    urls = [URL, URL.replace('www.buscalibre.com.co', 'www.panamericana.com.co')]
    result = await service(store).create_books(urls)
    assert [item['url'] for item in result['items']] == urls
    assert result['meta'] == {'total': 2}
    assert len(store.books) == 1
    assert len(store.relations) == len(store.history) == 2
    assert next(iter(store.books.values())).publisher == 'Fixture Publisher'


async def test_duplicate_relation_aborts_without_partial_state():
    store = InMemoryStore()
    with pytest.raises(BulkItemError) as exc:
        await service(store).create_books([URL, URL])
    # The API rejects identical strings first; application duplicate checks remain safe.
    assert exc.value.index == 1
    assert not store.books and not store.relations and not store.history


@pytest.mark.parametrize('failure', ['metadata', 'scraping'])
async def test_second_item_failure_preserves_previous_state(failure):
    store = InMemoryStore()
    await service(store).create_books([URL])
    previous = (dict(store.books), dict(store.relations), dict(store.history))
    class FailingMetadata(Metadata):
        async def enrich_by_isbn(self, isbn):
            if isbn == '3':
                raise RuntimeError('Metadata infrastructure unavailable')
            return await super().enrich_by_isbn(isbn)
    class FailingScraper(Scraper):
        async def scrape_book(self, store, url):
            if url.endswith('3'):
                raise ScrapingError('Scraping unavailable')
            return await super().scrape_book(store, url)
    kwargs = {'metadata': FailingMetadata()} if failure == 'metadata' else {'scraper': FailingScraper()}
    expected = RuntimeError if failure == 'metadata' else BulkItemError
    with pytest.raises(expected):
        await service(store, **kwargs).create_books([URL.replace('isbn-1', 'isbn-2'), URL.replace('isbn-1', 'isbn-3')])
    assert (store.books, store.relations, store.history) == previous
