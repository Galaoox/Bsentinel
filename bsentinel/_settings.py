from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración base de la aplicación bsentinel."""

    model_config = SettingsConfigDict(
        env_file="secrets/.env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Configuración de la aplicación
    app_name: str = "bsentinel"
    app_version: str = "1.0.0"
    app_environment: str = "local"  # local o production
    port: int = 8000
    log_level: str = "INFO"

    # Configuración de base de datos PostgreSQL
    database_url: str = "postgresql+asyncpg://bsentinel:bsentinel@localhost:5432/bsentinel"
    database_pool_size: int = 5
    database_max_overflow: int = 10

    # Configuración de scraping
    scraping_delay: float = 2.0  # Segundos entre peticiones a la misma tienda
    scraping_timeout: int = 30  # Timeout en segundos
    scraping_max_retries: int = 3

    # Configuración de OpenLibrary API
    openlibrary_api_url: str = "https://openlibrary.org"
    openlibrary_rate_limit: float = 1.0  # Segundos entre peticiones


settings = Settings()
