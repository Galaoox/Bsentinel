"""Request models for active v1 API routes."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CreateBookRequest(BaseModel):
    url: str = Field(min_length=10)


class CreateArchiveJobRequest(BaseModel):
    older_than_days: int = Field(default=365, ge=1)
    min_active_records_per_book: int = Field(default=1000, ge=1)


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=20)
