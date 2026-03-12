"""In-memory refresh token revocation repository."""

from __future__ import annotations

from datetime import datetime

from .store import InMemoryStore


class InMemoryRefreshTokenRepository:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    async def is_revoked(self, jti: str) -> bool:
        return jti in self.store.revoked_refresh_tokens

    async def revoke(self, *, jti: str, username: str, expires_at: datetime) -> None:
        self.store.revoked_refresh_tokens[jti] = {
            "username": username,
            "expires_at": expires_at,
        }
