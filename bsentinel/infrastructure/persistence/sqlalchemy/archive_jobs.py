"""SQLAlchemy archive job repository adapter."""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from uuid import UUID

from bsentinel.domain.dates import as_utc
from bsentinel.domain.models import ArchiveJob, now_utc
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from .mappers import to_archive_job
from .models import ArchiveJobModel, PriceHistoryArchiveModel, PriceHistoryModel


class SQLArchiveJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self) -> ArchiveJob:
        model = ArchiveJobModel(
            status="queued",
            started_at=None,
            finished_at=None,
            moved_records=0,
            errors="[]",
        )
        self.session.add(model)
        await self.session.flush()
        return to_archive_job(model)

    async def get(self, job_id: UUID) -> ArchiveJob | None:
        stmt = select(ArchiveJobModel).where(ArchiveJobModel.id == str(job_id))
        model = await self.session.scalar(stmt)
        if not model:
            return None
        return to_archive_job(model)

    async def run(self, job_id: UUID, older_than_days: int, min_active_records_per_book: int) -> ArchiveJob:
        stmt = select(ArchiveJobModel).where(ArchiveJobModel.id == str(job_id))
        job_model = await self.session.scalar(stmt)
        if not job_model:
            raise ValueError("Archive job not found")

        job_model.status = "running"
        job_model.started_at = now_utc()
        await self.session.flush()

        try:
            cutoff = now_utc() - timedelta(days=older_than_days)
            active_rows = await self.session.scalars(
                select(PriceHistoryModel).where(PriceHistoryModel.archived.is_(False))
            )
            by_book: dict[str, list[PriceHistoryModel]] = defaultdict(list)
            for row in active_rows.all():
                by_book[row.book_id].append(row)

            to_move: list[PriceHistoryModel] = []
            for rows in by_book.values():
                rows.sort(key=lambda r: (as_utc(r.checked_at), r.id), reverse=True)
                keep = rows[:min_active_records_per_book]
                keep_ids = {item.id for item in keep}
                for row in rows[min_active_records_per_book:]:
                    if as_utc(row.checked_at) < cutoff and row.id not in keep_ids:
                        to_move.append(row)

            for row in to_move:
                self.session.add(
                    PriceHistoryArchiveModel(
                        id=row.id,
                        book_id=row.book_id,
                        relation_id=row.relation_id,
                        store_id=row.store_id,
                        price=row.price,
                        state=row.state,
                        checked_at=row.checked_at,
                        archived=True,
                    )
                )

            if to_move:
                await self.session.execute(
                    delete(PriceHistoryModel).where(PriceHistoryModel.id.in_([row.id for row in to_move]))
                )

            job_model.moved_records = len(to_move)
            job_model.status = "completed"
            job_model.finished_at = now_utc()
            await self.session.flush()
        except Exception:
            await self.session.rollback()
            raise

        return to_archive_job(job_model)
