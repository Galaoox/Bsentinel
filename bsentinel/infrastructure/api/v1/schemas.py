"""Request models for v1 API routes."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class CreateBookRequest(BaseModel):
    url: str = Field(min_length=10)


class CreateArchiveJobRequest(BaseModel):
    older_than_days: int = Field(default=365, ge=1)
    min_active_records_per_book: int = Field(default=1000, ge=1)


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=20)


class ExtractionSourceRequest(BaseModel):
    kind: Literal["css", "json_ld"]
    selector: str | None = None
    attribute: str | None = None
    path: str | None = None
    regex: str | None = None
    normalizer: Literal["text_trim", "isbn_digits", "price_latam", "price_cop", "price_decimal", "price_cop_mixed", "availability_buscalibre"] | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> "ExtractionSourceRequest":
        if self.kind == "css":
            if not self.selector or not self.attribute:
                raise ValueError("css sources require selector and attribute")
            if self.path is not None:
                raise ValueError("css sources cannot define path")
        if self.kind == "json_ld":
            if not self.path:
                raise ValueError("json_ld sources require path")
            if self.selector is not None or self.attribute is not None:
                raise ValueError("json_ld sources cannot define selector or attribute")
        return self


class ExtractionFieldRequest(BaseModel):
    sources: list[ExtractionSourceRequest] = Field(min_length=1)


class StoreExtractionRulesRequest(BaseModel):
    title: ExtractionFieldRequest
    authors: ExtractionFieldRequest
    isbn: ExtractionFieldRequest
    price: ExtractionFieldRequest
    availability: ExtractionFieldRequest | None = None


class StoreCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    domain: str = Field(min_length=3, max_length=255)
    country_code: str = Field(min_length=2, max_length=2)
    scrape_interval_hours: int = Field(default=6, ge=1)
    is_active: bool = True
    extraction_rules: StoreExtractionRulesRequest


class StoreUpdateRequest(StoreCreateRequest):
    pass


class StorePatchRequest(BaseModel):
    is_active: bool | None = None
    scrape_interval_hours: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_any_field(self) -> "StorePatchRequest":
        if self.is_active is None and self.scrape_interval_hours is None:
            raise ValueError("At least one patch field is required")
        return self
