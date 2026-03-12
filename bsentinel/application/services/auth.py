"""Authentication application service."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import timedelta
from hmac import compare_digest

from bsentinel.application.ports import RefreshTokenRepositoryPort, TokenManagerPort
from bsentinel.exceptions import (
    ForbiddenError,
    InvalidCredentialsError,
    InvalidTokenError,
    RefreshTokenRevokedError,
)


@dataclass(slots=True)
class AuthenticatedUser:
    username: str
    role: str


@dataclass(slots=True)
class TokenPair:
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int


class AuthService:
    def __init__(
        self,
        *,
        admin_username: str,
        admin_password: str,
        token_manager: TokenManagerPort,
        refresh_tokens: RefreshTokenRepositoryPort,
        access_token_expire_minutes: int,
        refresh_token_expire_days: int,
    ) -> None:
        self.admin_username = admin_username
        self.admin_password = admin_password
        self.token_manager = token_manager
        self.refresh_tokens = refresh_tokens
        self.access_token_expire_minutes = access_token_expire_minutes
        self.refresh_token_expire_days = refresh_token_expire_days

    async def login(self, username: str, password: str) -> dict:
        self._validate_admin_credentials(username, password)
        return asdict(self._issue_token_pair())

    async def authenticate_access_token(self, token: str) -> AuthenticatedUser:
        payload = self.token_manager.decode_token(token, expected_type="access")
        return self._build_authenticated_user(payload)

    async def refresh(self, refresh_token: str) -> dict:
        payload = self.token_manager.decode_token(refresh_token, expected_type="refresh")
        user = self._build_authenticated_user(payload)

        if await self.refresh_tokens.is_revoked(payload["jti"]):
            raise RefreshTokenRevokedError("Refresh token has been revoked")

        await self.refresh_tokens.revoke(
            jti=payload["jti"],
            username=user.username,
            expires_at=payload["expires_at"],
        )
        return asdict(self._issue_token_pair())

    async def logout(self, refresh_token: str) -> None:
        payload = self.token_manager.decode_token(refresh_token, expected_type="refresh")
        user = self._build_authenticated_user(payload)

        if await self.refresh_tokens.is_revoked(payload["jti"]):
            return

        await self.refresh_tokens.revoke(
            jti=payload["jti"],
            username=user.username,
            expires_at=payload["expires_at"],
        )

    def _validate_admin_credentials(self, username: str, password: str) -> None:
        username_matches = compare_digest(username, self.admin_username)
        password_matches = compare_digest(password, self.admin_password)
        if not username_matches or not password_matches:
            raise InvalidCredentialsError("Invalid username or password")

    def _build_authenticated_user(self, payload: dict) -> AuthenticatedUser:
        if payload["sub"] != self.admin_username:
            raise InvalidTokenError("Token subject is not recognized")
        if payload["role"] != "admin":
            raise ForbiddenError("User does not have the required role")
        return AuthenticatedUser(username=payload["sub"], role=payload["role"])

    def _issue_token_pair(self) -> TokenPair:
        access_payload = self.token_manager.issue_token(
            subject=self.admin_username,
            role="admin",
            token_type="access",
            expires_delta=timedelta(minutes=self.access_token_expire_minutes),
        )
        refresh_payload = self.token_manager.issue_token(
            subject=self.admin_username,
            role="admin",
            token_type="refresh",
            expires_delta=timedelta(days=self.refresh_token_expire_days),
        )
        return TokenPair(
            access_token=access_payload["token"],
            refresh_token=refresh_payload["token"],
            token_type="bearer",
            expires_in=int(timedelta(minutes=self.access_token_expire_minutes).total_seconds()),
        )
