"""Request models for active v1 API routes."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, field_validator


class CreateBooksBulkRequest(BaseModel):
    urls: list[Annotated[str, StringConstraints(strict=True, max_length=2048)]] = Field(
        min_length=1, max_length=20
    )

    @field_validator("urls")
    @classmethod
    def unique_urls(cls, urls: list[str]) -> list[str]:
        if len(set(urls)) != len(urls):
            raise ValueError("Duplicate URLs are not allowed")
        return urls


class CreateBookBulkItem(BaseModel):
    index: int
    url: str
    book_id: str
    relation_id: str
    isbn: str
    title: str
    authors: list[str]
    site: str
    status: str


class BulkMeta(BaseModel):
    total: int


class CreateBooksBulkResponse(BaseModel):
    items: list[CreateBookBulkItem]
    meta: BulkMeta


class CreateBookRequest(BaseModel):
    url: str = Field(min_length=10)


class CreateArchiveJobRequest(BaseModel):
    older_than_days: int = Field(default=365, ge=1)
    min_active_records_per_book: int = Field(default=1000, ge=1)


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=20)
