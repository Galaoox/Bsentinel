"""Authentication routes and dependencies for API v1."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from bsentinel.application.services import AuthService
from bsentinel.exceptions import ForbiddenError

from .schemas import RefreshTokenRequest

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def _http_auth_error(code: str, message: str, status_code: int = status.HTTP_401_UNAUTHORIZED) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
        headers={"WWW-Authenticate": "Bearer"},
    )


async def require_authenticated_user(
    auth_service: AuthService,
    token: Annotated[str | None, Depends(oauth2_scheme)],
) -> dict:
    if not token:
        raise _http_auth_error("AUTH_INVALID_TOKEN", "Authentication credentials were not provided")

    user = await auth_service.authenticate_access_token(token)
    return {"username": user.username, "role": user.role}


async def require_admin_user(
    auth_service: AuthService,
    token: Annotated[str | None, Depends(oauth2_scheme)],
) -> dict:
    user = await require_authenticated_user(auth_service, token)
    if user["role"] != "admin":
        raise ForbiddenError("User does not have the required role")
    return user


def build_auth_router(get_auth_service):
    router = APIRouter(prefix="/auth", tags=["auth"])

    @router.post("/login")
    async def login(
        form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
        auth_service: AuthService = Depends(get_auth_service),
    ):
        return await auth_service.login(form_data.username, form_data.password)

    @router.post("/refresh")
    async def refresh(
        payload: RefreshTokenRequest,
        auth_service: AuthService = Depends(get_auth_service),
    ):
        return await auth_service.refresh(payload.refresh_token)

    @router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
    async def logout(
        payload: RefreshTokenRequest,
        auth_service: AuthService = Depends(get_auth_service),
    ):
        await auth_service.logout(payload.refresh_token)

    return router


def build_authenticated_dependency(get_auth_service):
    async def dependency(
        auth_service: AuthService = Depends(get_auth_service),
        token: Annotated[str | None, Depends(oauth2_scheme)] = None,
    ) -> dict:
        return await require_authenticated_user(auth_service, token)

    return dependency


def build_admin_dependency(get_auth_service):
    async def dependency(
        auth_service: AuthService = Depends(get_auth_service),
        token: Annotated[str | None, Depends(oauth2_scheme)] = None,
    ) -> dict:
        return await require_admin_user(auth_service, token)

    return dependency
