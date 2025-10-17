"""Excepciones personalizadas para bsentinel."""


class StandardException(Exception):
    """Excepción base para la aplicación.
    
    Todas las excepciones personalizadas deben heredar de esta clase.
    """


class EntityDoesNotExistError(StandardException):
    """Se lanza cuando una entidad no existe en la base de datos."""


class EntityAlreadyExistsError(StandardException):
    """Se lanza cuando una entidad ya existe en la base de datos."""


class OperationNotAllowedError(StandardException):
    """Se lanza cuando una operación no está permitida."""


class ExternalServiceError(StandardException):
    """Se lanza cuando un servicio externo no está disponible (ej: OpenLibrary API)."""


class DatabaseError(StandardException):
    """Se lanza cuando hay un error en la base de datos."""


class ScrapingError(StandardException):
    """Se lanza cuando hay un error durante el proceso de scraping."""


class InvalidURLError(StandardException):
    """Se lanza cuando una URL es inválida o malformada."""


class UnsupportedStoreError(StandardException):
    """Se lanza cuando se intenta scrapear una tienda no soportada."""


class ValidationError(StandardException):
    """Se lanza cuando falla la validación de datos.""" in the authentication process.
    """
