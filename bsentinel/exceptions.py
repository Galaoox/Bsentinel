class StandardException(Exception):
    """
    Base exception for the application.
    Your `raise` statements should raise this exception or ideally one of its children.
    """


class EntityDoesNotExistError(StandardException):
    """
    Raised when an entity does not exist in the database.
    """


class EntityAlreadyExistsError(StandardException):
    """
    Raised when an entity already exists in the database.
    """


class OperationNotAllowedError(StandardException):
    """
    Raised when an operation is not allowed, like delete in most cases.
    """


class ExternalServiceError(StandardException):
    """
    Raised when an external service is not available, like an external API.
    """


class DatabaseError(StandardException):
    """
    Raised when there is an error in the database.
    """


class AuthenticationError(StandardException):
    """
    Raised when there is an error in the authentication process.
    """
