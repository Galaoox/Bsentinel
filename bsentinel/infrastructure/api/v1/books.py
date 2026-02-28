"""Book management routes for API v1."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from bsentinel.application.services import BookService
from bsentinel.exceptions import EntityAlreadyExistsError, EntityDoesNotExistError, UnsupportedStoreError, ValidationError

from .schemas import CreateBookRequest


def build_books_router(get_service):
    router = APIRouter(tags=["books"])

    @router.post("/books", status_code=status.HTTP_201_CREATED)
    async def create_book(payload: CreateBookRequest, service: BookService = Depends(get_service)):
        try:
            book, relation = await service.create_book_from_url(payload.url)
        except (ValidationError, UnsupportedStoreError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except EntityAlreadyExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        return {
            "book_id": str(book.id),
            "relation_id": str(relation.id),
            "isbn": book.isbn,
            "title": book.title,
            "authors": book.authors,
            "site": "www.buscalibre.com.co",
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
        service: BookService = Depends(get_service),
    ):
        return service.list_books(
            include_deleted=include_deleted,
            q=q,
            isbn=isbn,
            author=author,
            category=category,
            page=page,
            limit=limit,
        )

    @router.get("/books/{book_id}")
    async def get_book(book_id: UUID, service: BookService = Depends(get_service)):
        try:
            return service.get_book_detail(book_id)
        except EntityDoesNotExistError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.delete("/books/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_book(book_id: UUID, service: BookService = Depends(get_service)):
        try:
            service.delete_book(book_id)
        except EntityDoesNotExistError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/books/{book_id}/restore")
    async def restore_book(book_id: UUID, service: BookService = Depends(get_service)):
        try:
            return service.restore_book(book_id)
        except EntityDoesNotExistError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValidationError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    return router
