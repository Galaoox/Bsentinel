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

    async def add(self, store: Store) -> None:
        self.session.add(
            StoreModel(
                id=str(store.id),
                name=store.name,
                domain=store.domain,
                country_code=store.country_code,
                scrape_interval_hours=store.scrape_interval_hours,
                is_active=store.is_active,
                extraction_rules=store.extraction_rules,
                is_deleted=store.is_deleted,
                created_at=store.created_at,
                deleted_at=store.deleted_at,
            )
        )
        await self.session.flush()

    async def save(self, store: Store) -> None:
        model = await self.session.get(StoreModel, str(store.id))
        if model is None:
            await self.add(store)
            return

        model.name = store.name
        model.domain = store.domain
        model.country_code = store.country_code
        model.scrape_interval_hours = store.scrape_interval_hours
        model.is_active = store.is_active
        model.extraction_rules = store.extraction_rules
        model.is_deleted = store.is_deleted
        model.deleted_at = store.deleted_at
        await self.session.flush()

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
