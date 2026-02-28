"""Pricing and scraping application services."""

from __future__ import annotations

from math import ceil
from uuid import UUID

from bsentinel.application.ports import (
    BookRepositoryPort,
    HistoryRepositoryPort,
    RelationRepositoryPort,
    ScraperPort,
    StoreRepositoryPort,
)
from bsentinel.domain.models import BookStoreRelation, PriceHistoryRecord
from bsentinel.exceptions import EntityDoesNotExistError


class ScrapingService:
    def __init__(
        self,
        *,
        books: BookRepositoryPort,
        relations: RelationRepositoryPort,
        history: HistoryRepositoryPort,
        scraper: ScraperPort,
    ) -> None:
        self.books = books
        self.relations = relations
        self.history = history
        self.scraper = scraper

    async def scrape_relation(self, relation: BookStoreRelation) -> None:
        result = await self.scraper.scrape_book(relation.product_url)
        relation.current_price = result.price
        relation.status = result.status
        relation.last_checked = result.checked_at

        record = PriceHistoryRecord(
            book_id=relation.book_id,
            relation_id=relation.id,
            store_id=relation.store_id,
            price=result.price,
            state=result.status,
            checked_at=result.checked_at,
        )
        self.history.add(record)

    async def scrape_all_active(self) -> int:
        total = 0
        for relation in self.relations.list_all():
            book = self.books.get(relation.book_id)
            if book and not book.is_deleted:
                await self.scrape_relation(relation)
                total += 1
        return total


class PricingQueryService:
    def __init__(
        self,
        *,
        books: BookRepositoryPort,
        stores: StoreRepositoryPort,
        relations: RelationRepositoryPort,
        history: HistoryRepositoryPort,
    ) -> None:
        self.books = books
        self.stores = stores
        self.relations = relations
        self.history = history

    def get_history(
        self,
        *,
        book_id: UUID,
        source: str,
        state: str | None,
        start_date,
        end_date,
        page: int,
        limit: int,
    ) -> dict:
        if not self.books.get(book_id):
            raise EntityDoesNotExistError("Book not found")

        records = self.history.list(
            book_id=book_id,
            source=source,
            state=state,
            start_date=start_date,
            end_date=end_date,
        )
        total = len(records)
        start = (page - 1) * limit
        paginated = records[start : start + limit]

        output = []
        for record in paginated:
            store = self.stores.get(record.store_id)
            output.append(
                {
                    "price": record.price,
                    "state": record.state,
                    "checked_at": record.checked_at,
                    "domain": store.domain if store else "unknown",
                    "archived": record.archived,
                }
            )

        return {
            "book_id": str(book_id),
            "records": output,
            "meta": {
                "total": total,
                "page": page,
                "limit": limit,
                "pages": ceil(total / limit) if total else 0,
            },
        }

    def get_price_comparison(self, book_id: UUID) -> dict:
        if not self.books.get(book_id):
            raise EntityDoesNotExistError("Book not found")

        offers = []
        for relation in self.relations.list_for_book(book_id):
            if relation.status != "activo" or relation.current_price is None:
                continue

            store = self.stores.get(relation.store_id)
            offers.append(
                {
                    "domain": store.domain if store else "unknown",
                    "price": relation.current_price,
                    "status": relation.status,
                }
            )

        offers.sort(key=lambda item: item["price"])
        return {"book_id": str(book_id), "best_offer": offers[0] if offers else None, "offers": offers}
