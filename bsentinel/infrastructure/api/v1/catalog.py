"""Catalog routes for API v1."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from bsentinel.application.services import (
    CatalogCommandService,
    CatalogQueryService,
    ScrapingService,
)
from bsentinel.application.services.catalog_bulk import CatalogBulkService

from .schemas import CreateBookRequest, CreateBooksBulkRequest, CreateBooksBulkResponse


def build_catalog_router(get_command_service, get_query_service, get_scraping_service, get_bulk_service):
    router = APIRouter(prefix="/catalog", tags=["catalog"])

    @router.post("/books/bulk", status_code=status.HTTP_201_CREATED,
                 response_model=CreateBooksBulkResponse,
                 responses={code: {"description": description} for code, description in [
                     (400, "Invalid item or scraping failure"), (401, "JWT required"),
                     (409, "Duplicate book-store relation"), (422, "Invalid request"),
                     (500, "Persistence or infrastructure failure")]})
    async def create_books_bulk(
        payload: CreateBooksBulkRequest,
        service: CatalogBulkService = Depends(get_bulk_service),
    ):
        return await service.create_books(payload.urls)

    @router.post("/books", status_code=status.HTTP_201_CREATED)
    async def create_book(
        payload: CreateBookRequest,
        command_service: CatalogCommandService = Depends(get_command_service),
        scraping_service: ScrapingService = Depends(get_scraping_service),
    ):
        book, relation, store_domain, result = await command_service.create_book_from_url(payload.url)
        await scraping_service.record_result(relation, result)

        return {
            "book_id": str(book.id),
            "relation_id": str(relation.id),
            "isbn": book.isbn,
            "title": book.title,
            "authors": book.authors,
            "site": store_domain,
            "status": relation.status,
        }

    @router.get("/books")
    async def list_books(
        include_deleted: bool = False,
        q: str | None = None,
        isbn: str | None = None,
        author: str | None = None,
        category: str | None = None,
        page: int = Query(default=1, ge=1),
        limit: int = Query(default=50, ge=1, le=200),
        query_service: CatalogQueryService = Depends(get_query_service),
    ):
        return await query_service.list_books(
            include_deleted=include_deleted,
            q=q,
            isbn=isbn,
            author=author,
            category=category,
            page=page,
            limit=limit,
        )

    @router.get("/books/{book_id}")
    async def get_book(book_id: UUID, query_service: CatalogQueryService = Depends(get_query_service)):
        return await query_service.get_book_detail(book_id)

    @router.delete("/books/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_book(book_id: UUID, command_service: CatalogCommandService = Depends(get_command_service)):
        await command_service.delete_book(book_id)

    @router.post("/books/{book_id}/restore")
    async def restore_book(book_id: UUID, command_service: CatalogCommandService = Depends(get_command_service)):
        return await command_service.restore_book(book_id)

    return router
