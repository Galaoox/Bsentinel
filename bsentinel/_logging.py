"""Configuración de logging para bsentinel."""

import logging
import logging.config

from pythonjsonlogger.jsonlogger import JsonFormatter

from ._logging_context import RequestContextFilter
from ._settings import settings

config = {
    "disable_existing_loggers": False,
    "version": 1,
    "formatters": {
        "json": {
            "()": lambda: JsonFormatter(
                # Available attributes
                # https://docs.python.org/3/library/logging.html#logrecord-attributes
                fmt="%(asctime)s %(levelname)s %(message)s %(name)s %(request_id)s",
                rename_fields={"name": "logger.name"},
                json_indent=2 if settings.app_environment == "local" else None,
            )
        },
    },
    "filters": {
        "request_context": {
            "()": RequestContextFilter,
        },
    },
    "handlers": {
        "console": {
            "formatter": "json",
            "class": "logging.StreamHandler",
            "filters": ["request_context"],
        },
    },
    "root": {
        "level": settings.log_level,
        "handlers": ["console"],
    },
    "loggers": {
        "uvicorn": {
            "propagate": True,
        },
        "sqlalchemy.engine": {
            "level": "WARNING",
        },
        "scrapy": {
            "level": "INFO",
        },
    },
}


def configure_logging() -> None:
    """Configura el sistema de logging de la aplicación."""
    logging.config.dictConfig(config)
    logger = logging.getLogger(__name__)
    logger.info(
        f"Logging configured with APP_ENVIRONMENT={settings.app_environment}, "
        f"LOG_LEVEL={settings.log_level}"
    )
