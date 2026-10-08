"""SQLAlchemy store repository adapter."""

from __future__ import annotations

from uuid import UUID

from bsentinel.domain.models import Store, now_utc
from bsentinel.domain.scraping_schedule import initial_check
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .mappers import to_relation, to_store
from .models import BookStoreRelationModel, StoreModel


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
        # Lock the parent before relation rows, matching result publication.
        model = await self.session.scalar(select(StoreModel).where(StoreModel.id == str(store.id)).with_for_update(key_share=True).execution_options(populate_existing=True))
        if model is None:
            await self.add(store)
            return

        reactivated = (not model.is_active or model.is_deleted) and store.is_active and not store.is_deleted
        model.name = store.name
        model.domain = store.domain
        model.country_code = store.country_code
        model.scrape_interval_hours = store.scrape_interval_hours
        model.is_active = store.is_active
        model.extraction_rules = store.extraction_rules
        model.is_deleted = store.is_deleted
        model.deleted_at = store.deleted_at
        await self.session.flush()
        if reactivated:
            now = now_utc()
            rows = await self.session.scalars(select(BookStoreRelationModel).where(BookStoreRelationModel.store_id == str(store.id)).order_by(BookStoreRelationModel.id).with_for_update().execution_options(populate_existing=True))
            for row in rows:
                relation = to_relation(row)
                if relation.scrape_group is not None:
                    row.scrape_generation += 1
                    row.next_check_at = initial_check(relation.scrape_group, now, relation.last_checked)
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
