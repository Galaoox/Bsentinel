"""Run creation publication and rollback on SQLite or disposable PostgreSQL."""
import json
from collections import Counter
from datetime import UTC, timedelta

import pytest
from scrapling.engines.toolbelt.custom import Response
from sqlalchemy import func, select

from bsentinel.application.services.catalog import CatalogCommandService
from bsentinel.application.services.catalog_bulk import CatalogBulkService
from bsentinel.application.services.pricing import ScrapingService
from bsentinel.domain.models import Store
from bsentinel.exceptions import BulkItemError
from bsentinel.infrastructure.persistence.sqlalchemy import (
    SQLBookRepository,
    SQLHistoryRepository,
    SQLRelationRepository,
    SQLStoreRepository,
)
from bsentinel.infrastructure.persistence.sqlalchemy.models import (
    BookModel,
    BookStoreRelationModel,
    PriceHistoryModel,
)
from bsentinel.infrastructure.persistence.sqlalchemy.transactions import SQLCatalogTransaction
from bsentinel.infrastructure.scraping.configured import ConfiguredStoreScraper
from bsentinel.infrastructure.scraping.rules import (
    build_default_buscalibre_rules,
    build_default_panamericana_rules,
)


@pytest.mark.parametrize('failure', [False, True])
async def test_sql_bulk_publishes_one_initial_result_or_rolls_back_every_item(schedule_db, failure):
    factory, _ = schedule_db
    urls = ['https://buscalibre.com.co/book/p', 'https://panamericana.com.co/book/p']
    calls, enrichments = [], []

    class Session:
        async def fetch(self, url):
            calls.append(url)
            price = -1 if failure and 'panamericana' in url else 45900
            product = {'@type': 'Product', '@id': url, 'name': 'SQL fixture',
                       'isbn': '9780321146533', 'author': [{'name': 'Kent Beck'}],
                       'offers': {'price': price, 'lowPrice': price,
                                  'availability': 'http://schema.org/InStock'}}
            return Response(url=url, content='<html><script type="application/ld+json">'
                            + json.dumps(product) + '</script></html>', status=200, reason='OK',
                            cookies={}, headers={'content-type': 'text/html'},
                            request_headers={}, encoding='utf-8')

    class Metadata:
        async def enrich_by_isbn(self, isbn):
            enrichments.append(isbn)
            return {}

    async with factory() as session:
        stores = SQLStoreRepository(session)
        await stores.add(Store(domain='www.buscalibre.com.co', extraction_rules=build_default_buscalibre_rules()))
        await stores.add(Store(domain='www.panamericana.com.co', extraction_rules=build_default_panamericana_rules()))
        await session.commit()
    async with factory() as session:
        books, stores = SQLBookRepository(session), SQLStoreRepository(session)
        relations, history = SQLRelationRepository(session), SQLHistoryRepository(session)
        scraper = ConfiguredStoreScraper(browser_session=Session())
        command = CatalogCommandService(books=books, stores=stores, relations=relations,
                                        metadata=Metadata(), scraper=scraper)
        pricing = ScrapingService(books=books, stores=stores, relations=relations,
                                 history=history, scraper=scraper)
        bulk = CatalogBulkService(command, pricing, SQLCatalogTransaction(session))
        if failure:
            with pytest.raises(BulkItemError) as error:
                await bulk.create_books(urls)
            assert error.value.index == 1
        else:
            result = await bulk.create_books(urls)
            assert [item['url'] for item in result['items']] == urls
    # Read back from an independent session, not the publisher's identity map.
    async with factory() as session:
        counts = tuple([await session.scalar(select(func.count()).select_from(model))
                        for model in [BookModel, BookStoreRelationModel, PriceHistoryModel]])
        assert counts == ((1, 0, 0) if failure else (2, 2, 2))  # schedule_db seeded one unrelated book
        rows = list(await session.scalars(select(BookStoreRelationModel)))
        records = list(await session.scalars(select(PriceHistoryModel)))
        for row in rows:
            record = next(r for r in records if r.relation_id == row.id)
            assert row.last_checked == record.checked_at
            assert row.current_price == record.price == 45900
            assert row.scrape_generation == 0
            assert row.next_check_at.replace(tzinfo=UTC) >= row.last_checked.replace(tzinfo=UTC) + timedelta(hours=1)
    assert Counter(calls) == {url.replace('://', '://www.'): 1 for url in urls}
    assert enrichments == ['9780321146533']
