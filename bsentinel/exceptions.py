"""Excepciones personalizadas para bsentinel."""


class StandardException(Exception):
    """Excepción base para la aplicación."""


class EntityDoesNotExistError(StandardException):
    """Se lanza cuando una entidad no existe."""


class EntityAlreadyExistsError(StandardException):
    """Se lanza cuando una entidad ya existe."""


class OperationNotAllowedError(StandardException):
    """Se lanza cuando una operación no está permitida."""


class ExternalServiceError(StandardException):
    """Se lanza cuando un servicio externo no está disponible."""


class DatabaseError(StandardException):
    """Se lanza cuando hay un error en la base de datos."""


class ScrapingError(StandardException):
    """Se lanza cuando hay un error durante scraping."""


class InvalidURLError(StandardException):
    """Se lanza cuando una URL es inválida."""


class UnsupportedStoreError(StandardException):
    """Se lanza cuando la tienda no está soportada."""


class ValidationError(StandardException):
    """Se lanza cuando falla la validación de datos."""
