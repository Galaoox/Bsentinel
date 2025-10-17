"""Configuración específica para el entorno local de desarrollo."""

from bsentinel._settings import Settings


class LocalSettings(Settings):
    """Configuración para entorno local."""
    
    app_environment: str = "local"
    log_level: str = "DEBUG"
    database_url: str = "postgresql+asyncpg://bsentinel:bsentinel@localhost:5432/bsentinel"
    
    # Configuración de desarrollo con reloading
    reload: bool = True
