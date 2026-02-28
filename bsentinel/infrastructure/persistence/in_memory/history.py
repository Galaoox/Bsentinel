"""In-memory history repository adapter."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from bsentinel.domain.models import PriceHistoryRecord

from .store import InMemoryStore


class InMemoryHistoryRepository:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    async def add(self, record: PriceHistoryRecord) -> None:
        self.store.history[record.id] = record

    async def list(
        self,
        *,
        book_id: UUID,
        source: str,
        state: str | None,
        start_date: datetime | None,
        end_date: datetime | None,
    ) -> list[PriceHistoryRecord]:
        records = [r for r in self.store.history.values() if r.book_id == book_id]

        if source == "active":
            records = [r for r in records if not r.archived]
        elif source == "archive":
            records = [r for r in records if r.archived]

        if state:
            records = [r for r in records if r.state == state]
        if start_date:
            records = [r for r in records if r.checked_at >= start_date]
        if end_date:
            records = [r for r in records if r.checked_at <= end_date]

        records.sort(key=lambda r: r.checked_at, reverse=True)
        return records
