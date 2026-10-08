"""Append-only traffic evidence, intentionally no FK to mutable catalog."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class TrafficEventModel(Base):
    __tablename__ = "scraping_traffic_events"
    __table_args__ = (
        Index("ix_traffic_date_scope", "observed_at", "scope"),
        Index("ix_traffic_batch_date", "batch_id", "observed_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    domain: Mapped[str] = mapped_column(String(255))
    outcome: Mapped[str] = mapped_column(String(24))
    http_status: Mapped[int | None] = mapped_column(Integer)
    completeness: Mapped[str] = mapped_column(String(24))
    scope: Mapped[str] = mapped_column(String(24))
    batch_id: Mapped[str | None] = mapped_column(String(36))
    relation_id: Mapped[str | None] = mapped_column(String(36))
    operation_id: Mapped[str | None] = mapped_column(String(36))
    download_bytes: Mapped[int | None] = mapped_column(BigInteger)
    upload_bytes: Mapped[int | None] = mapped_column(BigInteger)
    request_bytes: Mapped[int | None] = mapped_column(BigInteger)
    header_bytes: Mapped[int | None] = mapped_column(BigInteger)
    redirects: Mapped[int | None] = mapped_column(Integer)
