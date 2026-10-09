"""Sequential bulk creation using the individual catalog rules."""
from bsentinel.application.ports.transactions import CatalogTransactionPort
from bsentinel.application.services.catalog import CatalogCommandService
from bsentinel.application.services.pricing import ScrapingService
from bsentinel.exceptions import BulkItemError, StandardError


class CatalogBulkService:
    def __init__(self, command: CatalogCommandService, scraping: ScrapingService,
                 transaction: CatalogTransactionPort) -> None:
        self.command = command
        self.scraping = scraping
        self.transaction = transaction

    async def create_books(self, urls: list[str]) -> dict:
        items = []
        async with self.transaction:
            for index, url in enumerate(urls):
                try:
                    book, relation, domain, result = await self.command.create_book_from_url(url)
                    await self.scraping.record_result(relation, result)
                    await self.transaction.flush()
                except StandardError as exc:
                    raise BulkItemError(exc, index, url) from exc
                items.append({
                    "index": index, "url": url, "book_id": str(book.id),
                    "relation_id": str(relation.id), "isbn": book.isbn,
                    "title": book.title, "authors": book.authors,
                    "site": domain, "status": relation.status,
                })
        return {"items": items, "meta": {"total": len(items)}}
