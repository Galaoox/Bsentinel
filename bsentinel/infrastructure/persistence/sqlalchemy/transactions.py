"""Bulk owns the existing request transaction, including auth autobegin."""
from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession


class SQLCatalogTransaction:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def __aenter__(self) -> Self:
        self.session.info["bulk_owns_transaction"] = True
        return self

    async def flush(self) -> None:
        await self.session.flush()

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            await self.session.rollback()
            return
        try:
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
