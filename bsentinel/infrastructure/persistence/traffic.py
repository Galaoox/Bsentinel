"""SQL aggregate queries; writes use their own transaction, not price transactions."""

from dataclasses import asdict

from sqlalchemy import case, extract, func, select

from bsentinel.domain.traffic import project_traffic

from .sqlalchemy.models import BookModel, BookStoreRelationModel, StoreModel
from .sqlalchemy.traffic_model import TrafficEventModel as E


class SQLTrafficRepository:
    def __init__(self, session):
        self.session = session

    async def add(self, event):
        self.session.add(E(**asdict(event)))
        await self.session.flush()

    async def report(self, start, end, *, relation_count=None, scope=None, batch_id=None):
        filters = [E.observed_at >= start, E.observed_at < end]
        if scope is not None:
            filters.append(E.scope == scope)
        if batch_id is not None:
            filters.append(E.batch_id == batch_id)
        # GET request_size is used once. Upload is reported separately, NOT added:
        # the raw request_size contract must not cause body double-counting.
        byte_count = (
            func.coalesce(E.request_bytes, 0)
            + func.coalesce(E.header_bytes, 0)
            + func.coalesce(E.download_bytes, 0)
        )
        columns = [
            func.count().label("attempts"),
            func.coalesce(func.sum(byte_count), 0).label("known_bytes"),
            func.coalesce(func.sum(E.request_bytes), 0).label("sent_request_bytes"),
            func.coalesce(
                func.sum(func.coalesce(E.header_bytes, 0) + func.coalesce(E.download_bytes, 0)), 0
            ).label("received_http_bytes"),
            func.sum(case((E.outcome == "http_error", 1), else_=0)).label("http_error_attempts"),
            func.sum(case((E.http_status == 403, 1), else_=0)).label("http_403_attempts"),
            func.sum(case((E.completeness == "unknown", 1), else_=0)).label("unknown_attempts"),
            func.sum(case((E.completeness == "incomplete", 1), else_=0)).label(
                "incomplete_attempts"
            ),
            func.sum(case((E.outcome == "successful", 1), else_=0)).label("successful_attempts"),
            func.sum(case((E.outcome != "successful", 1), else_=0)).label("failed_attempts"),
        ]

        async def aggregate(groups=(), names=(), limit=None, extra_filters=()):
            query = select(*[g.label(n) for g, n in zip(groups, names)], *columns).where(
                *filters, *extra_filters
            )
            if groups:
                query = query.group_by(*groups).order_by(*groups)
            if limit:
                query = query.limit(limit)
            rows = (await self.session.execute(query)).mappings().all()
            return [
                {k: (int(v or 0) if k not in names else v) for k, v in row.items()} for row in rows
            ]

        observed = (await aggregate())[0]
        date_column = (
            func.timezone("UTC", E.observed_at)
            if self.session.bind.dialect.name == "postgresql"
            else E.observed_at
        )
        daily = await aggregate((func.date(date_column),), ("date",))
        monthly = await aggregate(
            (extract("year", date_column), extract("month", date_column)), ("year", "month")
        )
        batches = await aggregate((E.batch_id,), ("batch_id",), 101, (E.batch_id.is_not(None),))
        source = "requested" if relation_count is not None else "current_dataset"
        if relation_count is None:
            relation_count = (
                await self.session.execute(
                    select(func.count())
                    .select_from(BookStoreRelationModel)
                    .join(BookModel, BookModel.id == BookStoreRelationModel.book_id)
                    .join(StoreModel, StoreModel.id == BookStoreRelationModel.store_id)
                    .where(
                        BookModel.is_deleted.is_(False),
                        StoreModel.is_deleted.is_(False),
                        StoreModel.is_active.is_(True),
                        BookStoreRelationModel.next_check_at.is_not(None),
                    )
                )
            ).scalar_one()
        operations = (
            select(
                E.operation_id,
                func.sum(byte_count).label("bytes"),
                func.min(case((E.completeness == "known", 1), else_=0)).label("complete"),
            )
            .where(*filters, E.scope == "periodic", E.operation_id.is_not(None))
            .group_by(E.operation_id)
            .subquery()
        )
        sample = (
            await self.session.execute(
                select(func.count(), func.avg(operations.c.bytes)).where(operations.c.complete == 1)
            )
        ).one()
        count, mean = sample
        projection = project_traffic(
            sample_operations=count,
            mean_bytes=mean,
            relation_count=relation_count,
            relation_count_source=source,
        )
        from bsentinel.infrastructure.scraping import traffic

        return {
            "window": {"start": start.isoformat(), "end_exclusive": end.isoformat()},
            "observed": observed,
            "daily": daily,
            "monthly": monthly,
            "batches": batches[:100],
            "batches_truncated": len(batches) > 100,
            "projection": projection,
            "definition": "request_size + header_size + size_download_t; upload not added",
            "process_health": {
                "missing_writes_since_start": traffic.missing_writes,
                "unobserved_fetches_since_start": traffic.unobserved_fetches,
            },
            "completeness": "partial_http_accounting; missing writes unavailable historically; not wire or billing bytes",
        }
