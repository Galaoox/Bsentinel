"""Punto de entrada para ejecutar la aplicación."""

import uvicorn

from bsentinel import settings
from bsentinel._logging import configure_logging


def main() -> None:
    """Inicia el servidor FastAPI."""
    configure_logging()
    
    uvicorn.run(
        "bsentinel.infrastructure.api:root_app",
        host="0.0.0.0",
        port=settings.port,
        log_config=None,
        reload=(settings.app_environment == "local"),
    )


if __name__ == "__main__":
    main()
