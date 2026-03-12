"""Authentication-related application ports."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Protocol


class TokenManagerPort(Protocol):
    def issue_token(
        self,
        *,
        subject: str,
        role: str,
        token_type: str,
        expires_delta: timedelta,
    ) -> dict[str, Any]: ...

    def decode_token(self, token: str, *, expected_type: str) -> dict[str, Any]: ...


class RefreshTokenRepositoryPort(Protocol):
    async def is_revoked(self, jti: str) -> bool: ...

    async def revoke(self, *, jti: str, username: str, expires_at: datetime) -> None: ...
