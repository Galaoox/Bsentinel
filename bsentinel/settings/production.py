"""Configuración específica para el entorno de producción."""

from bsentinel._settings import Settings


class ProductionSettings(Settings):
    """Configuración para entorno de producción."""
    
    app_environment: str = "production"
    log_level: str = "INFO"
    
    # Configuración de producción sin reloading
    reload: bool = False
    
    # Pool de conexiones más grande para producción
    database_pool_size: int = 20
    database_max_overflow: int = 40
