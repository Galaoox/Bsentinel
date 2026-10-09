"""SQLAlchemy relation repository adapter."""

from __future__ import annotations

import asyncio
from datetime import datetime
from uuid import UUID

from bsentinel.domain.models import BookStoreRelation, now_utc
from bsentinel.domain.scraping_schedule import initial_check
from sqlalchemy import and_, event, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .mappers import to_relation
from .models import BookModel, BookStoreRelationModel, StoreModel

_assignment_lock = asyncio.Lock()


class SQLRelationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, relation_id: UUID) -> BookStoreRelation | None:
        model = await self.session.scalar(select(BookStoreRelationModel).where(BookStoreRelationModel.id == str(relation_id)))
        return to_relation(model) if model else None

    async def get_for_update(self, relation_id: UUID) -> BookStoreRelation | None:
        # Same parent-before-relation order as reactivation/restoration.
        # NO KEY UPDATE protects parent state without blocking bulk FK KEY SHARE.
        ids = (await self.session.execute(select(BookStoreRelationModel.store_id, BookStoreRelationModel.book_id).where(BookStoreRelationModel.id == str(relation_id)))).first()
        if ids is None:
            return None
        await self.session.scalar(select(StoreModel).where(StoreModel.id == ids.store_id).with_for_update(key_share=True).execution_options(populate_existing=True))
        await self.session.scalar(select(BookModel).where(BookModel.id == ids.book_id).with_for_update(key_share=True).execution_options(populate_existing=True))
        model = await self.session.scalar(select(BookStoreRelationModel).where(BookStoreRelationModel.id == str(relation_id)).with_for_update().execution_options(populate_existing=True))
        return to_relation(model) if model else None

    async def add(self, relation: BookStoreRelation) -> None:
        if relation.scrape_group is None:
            if not self.session.info.get("schedule_assignment_owned"):
                await _assignment_lock.acquire()
                self.session.info["schedule_assignment_owned"] = True
                def release(session, transaction):
                    if transaction.parent is None and session.info.pop("schedule_assignment_owned", False):
                        _assignment_lock.release()
                event.listen(self.session.sync_session, "after_transaction_end", release)
            await self.session.flush()
            r = BookStoreRelationModel
            counts = dict((await self.session.execute(select(r.scrape_group, func.count()).join(BookModel, BookModel.id == r.book_id).join(StoreModel, StoreModel.id == r.store_id).where(BookModel.is_deleted.is_(False), StoreModel.is_deleted.is_(False), StoreModel.is_active.is_(True)).group_by(r.scrape_group))).all())
            relation.scrape_group = min(range(3), key=lambda group: (counts.get(group, 0), group))
        if relation.next_check_at is None:
            relation.next_check_at = initial_check(relation.scrape_group, now_utc(), relation.last_checked)
        self.session.add(
            BookStoreRelationModel(
                id=str(relation.id),
                book_id=str(relation.book_id),
                store_id=str(relation.store_id),
                product_url=relation.product_url,
                current_price=relation.current_price,
                status=relation.status,
                last_checked=relation.last_checked,
                scrape_group=relation.scrape_group,
                next_check_at=relation.next_check_at,
                scrape_generation=relation.scrape_generation,
                created_at=relation.created_at,
            )
        )

    async def save(self, relation: BookStoreRelation) -> None:
        await self.session.flush()
        stmt = select(BookStoreRelationModel).where(BookStoreRelationModel.id == str(relation.id))
        model = await self.session.scalar(stmt)
        if not model:
            await self.add(relation)
            return

        model.book_id = str(relation.book_id)
        model.store_id = str(relation.store_id)
        if model.product_url != relation.product_url and relation.scrape_group is not None:
            relation.scrape_generation = model.scrape_generation + 1
            relation.next_check_at = initial_check(relation.scrape_group, now_utc(), relation.last_checked)
        model.product_url = relation.product_url
        model.current_price = relation.current_price
        model.status = relation.status
        model.last_checked = relation.last_checked
        model.scrape_group = relation.scrape_group
        model.next_check_at = relation.next_check_at
        model.scrape_generation = relation.scrape_generation

    async def list_for_book(self, book_id: UUID) -> list[BookStoreRelation]:
        stmt = select(BookStoreRelationModel).where(BookStoreRelationModel.book_id == str(book_id))
        result = await self.session.scalars(stmt.order_by(BookStoreRelationModel.created_at.asc()))
        return [to_relation(model) for model in result.all()]

    async def list_due(self, now: datetime, limit: int, after: tuple[datetime, UUID] | None = None) -> list[BookStoreRelation]:
        if limit < 1:
            raise ValueError("limit must be positive")
        relation = BookStoreRelationModel
        stmt = (select(relation).join(BookModel, BookModel.id == relation.book_id)
                .join(StoreModel, StoreModel.id == relation.store_id)
                .where(BookModel.is_deleted.is_(False), StoreModel.is_deleted.is_(False),
                       StoreModel.is_active.is_(True), relation.next_check_at <= now))
        if after is not None:
            timestamp, relation_id = after
            stmt = stmt.where(or_(relation.next_check_at > timestamp,
                             and_(relation.next_check_at == timestamp, relation.id > str(relation_id))))
        result = await self.session.scalars(stmt.order_by(relation.next_check_at, relation.id).limit(limit))
        return [to_relation(model) for model in result.all()]

    async def list_all(self) -> list[BookStoreRelation]:
        stmt = select(BookStoreRelationModel).order_by(BookStoreRelationModel.created_at.asc())
        result = await self.session.scalars(stmt)
        return [to_relation(model) for model in result.all()]
