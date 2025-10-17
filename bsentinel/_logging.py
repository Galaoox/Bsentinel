import logging
import logging.config

from pythonjsonlogger.jsonlogger import JsonFormatter

from ._settings import settings

config = {
    "disable_existing_loggers": True,
    "version": 1,
    "formatters": {
        "json": {
            "()": lambda: JsonFormatter(
                # Available attributes
                # https://docs.python.org/3/library/logging.html#logrecord-attributes
                fmt="%(asctime)s %(levelname)s %(message)s %(name)s",
                rename_fields={"name": "logger.name"},
                json_indent=2 if settings.app_environment == "local" else None,
            )
        },
    },
    "handlers": {
        "console": {
            "formatter": "json",
            "class": "logging.StreamHandler",
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
        # "uvicorn.access": {
        #     "level": "WARNING",
        # },
    },
}


def configure_logging():
    logging.config.dictConfig(config)
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured with APP_ENVIRONMENT={settings.app_environment}")
