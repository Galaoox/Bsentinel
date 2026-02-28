"""SQLAlchemy store repository adapter."""

from __future__ import annotations

from uuid import UUID

from bsentinel.domain.models import Store
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .mappers import to_store
from .models import StoreModel


class SQLStoreRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, store_id: UUID) -> Store | None:
        stmt = select(StoreModel).where(StoreModel.id == str(store_id))
        model = await self.session.scalar(stmt)
        if not model:
            return None
        return to_store(model)

    async def get_by_domain(self, domain: str) -> Store | None:
        stmt = select(StoreModel).where(StoreModel.domain == domain, StoreModel.is_deleted.is_(False))
        model = await self.session.scalar(stmt)
        if not model:
            return None
        return to_store(model)

    async def list(self) -> list[Store]:
        stmt = select(StoreModel).where(StoreModel.is_deleted.is_(False)).order_by(StoreModel.created_at.asc())
        result = await self.session.scalars(stmt)
        return [to_store(model) for model in result.all()]
