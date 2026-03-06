"""Mapping helpers between domain dataclasses and ORM models."""

from __future__ import annotations

import json
from uuid import UUID

from bsentinel.domain.models import ArchiveJob, Book, BookStoreRelation, PriceHistoryRecord, Store

from .models import (
    ArchiveJobModel,
    BookAuthorModel,
    BookCategoryModel,
    BookModel,
    BookStoreRelationModel,
    PriceHistoryArchiveModel,
    PriceHistoryModel,
    StoreModel,
)


def to_store(model: StoreModel) -> Store:
    return Store(
        id=UUID(model.id),
        name=model.name,
        domain=model.domain,
        country_code=model.country_code,
        scrape_interval_hours=model.scrape_interval_hours,
        is_active=model.is_active,
        is_deleted=model.is_deleted,
        created_at=model.created_at,
        deleted_at=model.deleted_at,
    )


def to_book(model: BookModel) -> Book:
    ordered_authors = [a.author for a in sorted(model.authors, key=lambda item: item.position)]
    ordered_categories = [c.category for c in sorted(model.categories, key=lambda item: item.position)]
    return Book(
        id=UUID(model.id),
        title=model.title,
        authors=ordered_authors,
        isbn=model.isbn,
        categories=ordered_categories,
        publisher=model.publisher,
        publication_year=model.publication_year,
        language=model.language,
        pages=model.pages,
        description=model.description,
        image_url=model.image_url,
        is_deleted=model.is_deleted,
        created_at=model.created_at,
        deleted_at=model.deleted_at,
    )


def to_relation(model: BookStoreRelationModel) -> BookStoreRelation:
    return BookStoreRelation(
        id=UUID(model.id),
        book_id=UUID(model.book_id),
        store_id=UUID(model.store_id),
        product_url=model.product_url,
        current_price=model.current_price,
        status=model.status,
        last_checked=model.last_checked,
        created_at=model.created_at,
    )


def to_history(model: PriceHistoryModel | PriceHistoryArchiveModel) -> PriceHistoryRecord:
    return PriceHistoryRecord(
        id=UUID(model.id),
        book_id=UUID(model.book_id),
        relation_id=UUID(model.relation_id),
        store_id=UUID(model.store_id),
        price=model.price,
        state=model.state,
        checked_at=model.checked_at,
        archived=model.archived,
    )


def to_archive_job(model: ArchiveJobModel) -> ArchiveJob:
    return ArchiveJob(
        id=UUID(model.id),
        status=model.status,
        started_at=model.started_at,
        finished_at=model.finished_at,
        moved_records=model.moved_records,
        errors=json.loads(model.errors),
    )


def apply_book_details(model: BookModel, book: Book) -> None:
    model.title = book.title
    model.isbn = book.isbn
    model.publisher = book.publisher
    model.publication_year = book.publication_year
    model.language = book.language
    model.pages = book.pages
    model.description = book.description
    model.image_url = book.image_url
    model.is_deleted = book.is_deleted
    model.deleted_at = book.deleted_at

    model.authors.clear()
    model.categories.clear()

    model.authors = [
        BookAuthorModel(book_id=model.id, position=index, author=author)
        for index, author in enumerate(book.authors)
    ]
    model.categories = [
        BookCategoryModel(book_id=model.id, position=index, category=category)
        for index, category in enumerate(book.categories)
    ]
