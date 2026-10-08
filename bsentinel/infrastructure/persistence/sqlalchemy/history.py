"""SQLAlchemy history repository adapter."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from bsentinel.domain.dates import as_utc
from bsentinel.domain.models import PriceHistoryRecord
from sqlalchemy import func, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

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

    def _query(self, *, book_id, source, state, start_date, end_date):
        selects = []
        for model, included in ((PriceHistoryModel, source in {"all", "active"}),
                                (PriceHistoryArchiveModel, source in {"all", "archive"})):
            if not included:
                continue
            stmt = select(*model.__table__.c).where(model.book_id == str(book_id))
            if state:
                stmt = stmt.where(model.state == state)
            if start_date:
                stmt = stmt.where(model.checked_at >= as_utc(start_date))
            if end_date:
                stmt = stmt.where(model.checked_at <= as_utc(end_date))
            selects.append(stmt)
        return union_all(*selects).subquery()

    @staticmethod
    def _record(row) -> PriceHistoryRecord:
        return PriceHistoryRecord(
            id=UUID(row.id), book_id=UUID(row.book_id), relation_id=UUID(row.relation_id),
            store_id=UUID(row.store_id), price=row.price, state=row.state,
            checked_at=row.checked_at, archived=row.archived,
        )

    async def list(self, *, book_id: UUID, source: str, state: str | None,
                   start_date: datetime | None, end_date: datetime | None) -> list[PriceHistoryRecord]:
        rows = self._query(book_id=book_id, source=source, state=state,
                           start_date=start_date, end_date=end_date)
        result = await self.session.execute(select(rows).order_by(rows.c.checked_at.desc(), rows.c.id.desc()))
        return [self._record(row) for row in result]

    async def list_page(self, *, book_id: UUID, source: str, state: str | None,
                        start_date: datetime | None, end_date: datetime | None,
                        page: int, limit: int) -> tuple[list[PriceHistoryRecord], int]:
        rows = self._query(book_id=book_id, source=source, state=state,
                           start_date=start_date, end_date=end_date)
        total = await self.session.scalar(select(func.count()).select_from(rows))
        result = await self.session.execute(
            select(rows).order_by(rows.c.checked_at.desc(), rows.c.id.desc())
            .limit(limit).offset((page - 1) * limit))
        return [self._record(row) for row in result], total
