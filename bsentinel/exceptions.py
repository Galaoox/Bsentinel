"""Excepciones personalizadas para bsentinel."""


class StandardError(Exception):
    """Excepción base para la aplicación."""


class EntityDoesNotExistError(StandardError):
    """Se lanza cuando una entidad no existe."""


class EntityAlreadyExistsError(StandardError):
    """Se lanza cuando una entidad ya existe."""


class OperationNotAllowedError(StandardError):
    """Se lanza cuando una operación no está permitida."""


class ExternalServiceError(StandardError):
    """Se lanza cuando un servicio externo no está disponible."""


class DatabaseError(StandardError):
    """Se lanza cuando hay un error en la base de datos."""


class ScrapingError(StandardError):
    """Se lanza cuando hay un error durante scraping."""

    def __init__(
        self,
        message: str,
        *,
        reason: str | None = None,
        diagnostics: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.diagnostics = diagnostics or {}


class InvalidURLError(StandardError):
    """Se lanza cuando una URL es inválida."""


class UnsupportedStoreError(StandardError):
    """Se lanza cuando la tienda no está soportada."""


class ValidationError(StandardError):
    """Se lanza cuando falla la validación de datos."""


class AuthenticationError(StandardError):
    """Se lanza cuando falla la autenticación."""

    code = "AUTH_ERROR"


class InvalidCredentialsError(AuthenticationError):
    """Se lanza cuando las credenciales no son válidas."""

    code = "AUTH_INVALID_CREDENTIALS"


class InvalidTokenError(AuthenticationError):
    """Se lanza cuando el token es inválido o expiró."""

    code = "AUTH_INVALID_TOKEN"


class RefreshTokenRevokedError(AuthenticationError):
    """Se lanza cuando el refresh token ya fue revocado."""

    code = "AUTH_REFRESH_REVOKED"


class ForbiddenError(StandardError):
    """Se lanza cuando el usuario no tiene permisos."""

    code = "AUTH_FORBIDDEN"


# Backward-compatible alias kept during migration.
StandardException = StandardError
