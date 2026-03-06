"""SQLAlchemy refresh token revocation repository."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import RevokedRefreshTokenModel


class SQLRefreshTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def is_revoked(self, jti: str) -> bool:
        stmt = select(RevokedRefreshTokenModel.jti).where(RevokedRefreshTokenModel.jti == jti)
        return await self.session.scalar(stmt) is not None

    async def revoke(self, *, jti: str, username: str, expires_at: datetime) -> None:
        existing = await self.session.get(RevokedRefreshTokenModel, jti)
        if existing is not None:
            return

        self.session.add(
            RevokedRefreshTokenModel(
                jti=jti,
                username=username,
                expires_at=expires_at,
                revoked_at=datetime.now(UTC),
            )
        )
