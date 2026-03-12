"""JWT token manager adapter."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt

from bsentinel.exceptions import InvalidTokenError


class JWTTokenManager:
    def __init__(self, *, secret_key: str, algorithm: str) -> None:
        self.secret_key = secret_key
        self.algorithm = algorithm

    def issue_token(
        self,
        *,
        subject: str,
        role: str,
        token_type: str,
        expires_delta: timedelta,
    ) -> dict:
        issued_at = datetime.now(UTC)
        expires_at = issued_at + expires_delta
        payload = {
            "sub": subject,
            "role": role,
            "type": token_type,
            "jti": str(uuid4()),
            "iat": issued_at,
            "exp": expires_at,
        }
        return {
            "token": jwt.encode(payload, self.secret_key, algorithm=self.algorithm),
            "jti": payload["jti"],
            "expires_at": expires_at,
        }

    def decode_token(self, token: str, *, expected_type: str) -> dict:
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
        except jwt.ExpiredSignatureError as exc:
            raise InvalidTokenError("Token expired") from exc
        except jwt.PyJWTError as exc:
            raise InvalidTokenError("Could not validate token") from exc

        token_type = payload.get("type")
        subject = payload.get("sub")
        role = payload.get("role")
        jti = payload.get("jti")
        expires_at = payload.get("exp")

        if token_type != expected_type:
            raise InvalidTokenError("Invalid token type")
        if not isinstance(subject, str) or not isinstance(role, str) or not isinstance(jti, str):
            raise InvalidTokenError("Token payload is incomplete")
        if isinstance(expires_at, (int, float)):
            expires_at = datetime.fromtimestamp(expires_at, UTC)
        if not isinstance(expires_at, datetime):
            raise InvalidTokenError("Token expiration is invalid")

        return {
            "sub": subject,
            "role": role,
            "jti": jti,
            "expires_at": expires_at,
        }
