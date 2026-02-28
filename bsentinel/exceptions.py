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


class InvalidURLError(StandardError):
    """Se lanza cuando una URL es inválida."""


class UnsupportedStoreError(StandardError):
    """Se lanza cuando la tienda no está soportada."""


class ValidationError(StandardError):
    """Se lanza cuando falla la validación de datos."""


# Backward-compatible alias kept during migration.
StandardException = StandardError
