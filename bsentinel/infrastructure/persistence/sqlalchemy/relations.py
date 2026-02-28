"""SQLAlchemy relation repository adapter."""

from __future__ import annotations

from uuid import UUID

from bsentinel.domain.models import BookStoreRelation
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .mappers import to_relation
from .models import BookStoreRelationModel


class SQLRelationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, relation: BookStoreRelation) -> None:
        self.session.add(
            BookStoreRelationModel(
                id=str(relation.id),
                book_id=str(relation.book_id),
                store_id=str(relation.store_id),
                product_url=relation.product_url,
                current_price=relation.current_price,
                status=relation.status,
                last_checked=relation.last_checked,
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
        model.product_url = relation.product_url
        model.current_price = relation.current_price
        model.status = relation.status
        model.last_checked = relation.last_checked

    async def list_for_book(self, book_id: UUID) -> list[BookStoreRelation]:
        stmt = select(BookStoreRelationModel).where(BookStoreRelationModel.book_id == str(book_id))
        result = await self.session.scalars(stmt.order_by(BookStoreRelationModel.created_at.asc()))
        return [to_relation(model) for model in result.all()]

    async def list_all(self) -> list[BookStoreRelation]:
        stmt = select(BookStoreRelationModel).order_by(BookStoreRelationModel.created_at.asc())
        result = await self.session.scalars(stmt)
        return [to_relation(model) for model in result.all()]
