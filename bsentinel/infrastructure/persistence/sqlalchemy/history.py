"""SQLAlchemy history repository adapter."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from bsentinel.domain.models import PriceHistoryRecord
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .mappers import to_history
from .models import PriceHistoryArchiveModel, PriceHistoryModel


class SQLHistoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, record: PriceHistoryRecord) -> None:
        self.session.add(
            PriceHistoryModel(
                id=str(record.id),
                book_id=str(record.book_id),
                relation_id=str(record.relation_id),
                store_id=str(record.store_id),
                price=record.price,
                state=record.state,
                checked_at=record.checked_at,
                archived=False,
            )
        )

    async def list(
        self,
        *,
        book_id: UUID,
        source: str,
        state: str | None,
        start_date: datetime | None,
        end_date: datetime | None,
    ) -> list[PriceHistoryRecord]:
        records: list[PriceHistoryRecord] = []
        include_active = source in {"all", "active"}
        include_archive = source in {"all", "archive"}

        if include_active:
            stmt_active = select(PriceHistoryModel).where(PriceHistoryModel.book_id == str(book_id))
            if state:
                stmt_active = stmt_active.where(PriceHistoryModel.state == state)
            if start_date:
                stmt_active = stmt_active.where(PriceHistoryModel.checked_at >= start_date)
            if end_date:
                stmt_active = stmt_active.where(PriceHistoryModel.checked_at <= end_date)
            active_result = await self.session.scalars(stmt_active)
            records.extend(to_history(model) for model in active_result.all())

        if include_archive:
            stmt_archive = select(PriceHistoryArchiveModel).where(
                PriceHistoryArchiveModel.book_id == str(book_id)
            )
            if state:
                stmt_archive = stmt_archive.where(PriceHistoryArchiveModel.state == state)
            if start_date:
                stmt_archive = stmt_archive.where(PriceHistoryArchiveModel.checked_at >= start_date)
            if end_date:
                stmt_archive = stmt_archive.where(PriceHistoryArchiveModel.checked_at <= end_date)
            archive_result = await self.session.scalars(stmt_archive)
            records.extend(to_history(model) for model in archive_result.all())

        records.sort(key=lambda item: item.checked_at, reverse=True)
        return records
