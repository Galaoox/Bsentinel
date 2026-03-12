import pytest

from bsentinel.application.services.auth import AuthService
from bsentinel.exceptions import InvalidCredentialsError, RefreshTokenRevokedError
from bsentinel.infrastructure.persistence.in_memory import (
    InMemoryRefreshTokenRepository,
    InMemoryStore,
)
from bsentinel.infrastructure.security import JWTTokenManager


@pytest.fixture
def auth_service():
    store = InMemoryStore()
    token_manager = JWTTokenManager(secret_key="test-secret-with-32-bytes-minimum", algorithm="HS256")
    return AuthService(
        admin_username="admin",
        admin_password="changeme",
        token_manager=token_manager,
        refresh_tokens=InMemoryRefreshTokenRepository(store),
        access_token_expire_minutes=60,
        refresh_token_expire_days=7,
    )


@pytest.mark.asyncio
async def test_login_rejects_invalid_credentials(auth_service):
    with pytest.raises(InvalidCredentialsError):
        await auth_service.login("admin", "bad-password")


@pytest.mark.asyncio
async def test_login_and_access_authentication(auth_service):
    tokens = await auth_service.login("admin", "changeme")
    user = await auth_service.authenticate_access_token(tokens["access_token"])

    assert user.username == "admin"
    assert user.role == "admin"


@pytest.mark.asyncio
async def test_refresh_revokes_previous_refresh_token(auth_service):
    tokens = await auth_service.login("admin", "changeme")
    rotated = await auth_service.refresh(tokens["refresh_token"])

    with pytest.raises(RefreshTokenRevokedError):
        await auth_service.refresh(tokens["refresh_token"])

    assert rotated["refresh_token"] != tokens["refresh_token"]
