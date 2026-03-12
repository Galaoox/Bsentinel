"""SQLAlchemy book repository adapter."""

from __future__ import annotations

from uuid import UUID

from bsentinel.domain.models import Book
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .mappers import apply_book_details, to_book
from .models import BookAuthorModel, BookCategoryModel, BookModel


class SQLBookRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, book: Book) -> None:
        existing = await self.session.get(
            BookModel,
            str(book.id),
            options=(selectinload(BookModel.authors), selectinload(BookModel.categories)),
        )
        if existing:
            existing.title = book.title
            existing.isbn = book.isbn
            existing.publisher = book.publisher
            existing.publication_year = book.publication_year
            existing.language = book.language
            existing.pages = book.pages
            existing.description = book.description
            existing.image_url = book.image_url
            existing.is_deleted = book.is_deleted
            existing.deleted_at = book.deleted_at

            current_authors = [author.author for author in sorted(existing.authors, key=lambda item: item.position)]
            if current_authors != book.authors:
                existing.authors.clear()
                await self.session.flush()
                existing.authors = [
                    BookAuthorModel(book_id=existing.id, position=index, author=author)
                    for index, author in enumerate(book.authors)
                ]

            current_categories = [
                category.category for category in sorted(existing.categories, key=lambda item: item.position)
            ]
            if current_categories != book.categories:
                existing.categories.clear()
                await self.session.flush()
                existing.categories = [
                    BookCategoryModel(book_id=existing.id, position=index, category=category)
                    for index, category in enumerate(book.categories)
                ]
            return

        model = BookModel(id=str(book.id), created_at=book.created_at)
        apply_book_details(model, book)
        self.session.add(model)

    async def get(self, book_id: UUID) -> Book | None:
        stmt = (
            select(BookModel)
            .where(BookModel.id == str(book_id))
            .options(selectinload(BookModel.authors), selectinload(BookModel.categories))
        )
        model = await self.session.scalar(stmt)
        if not model:
            return None
        return to_book(model)

    async def get_by_isbn(self, isbn: str) -> Book | None:
        stmt = (
            select(BookModel)
            .where(BookModel.isbn == isbn)
            .options(selectinload(BookModel.authors), selectinload(BookModel.categories))
        )
        model = await self.session.scalar(stmt)
        if not model:
            return None
        return to_book(model)

    async def list(self, *, include_deleted: bool = False) -> list[Book]:
        stmt = select(BookModel).options(selectinload(BookModel.authors), selectinload(BookModel.categories))
        if not include_deleted:
            stmt = stmt.where(BookModel.is_deleted.is_(False))
        result = await self.session.scalars(stmt.order_by(BookModel.created_at.desc()))
        return [to_book(model) for model in result.all()]
