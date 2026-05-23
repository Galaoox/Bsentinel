from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración base de la aplicación bsentinel."""

    model_config = SettingsConfigDict(
        env_file="secrets/.env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Configuración de la aplicación
    app_name: str = "bsentinel"
    app_version: str = "1.0.0"
    app_environment: str = "local"  # local o production
    port: int = 8000
    log_level: str = "INFO"
    persistence_backend: str = "sql"  # sql | in_memory

    # Configuración de base de datos PostgreSQL
    database_url: str = "postgresql+asyncpg://bsentinel:bsentinel@localhost:5432/bsentinel"
    database_pool_size: int = 5
    database_max_overflow: int = 10

    # Configuración de scraping
    scraping_delay: float = 2.0  # Segundos entre peticiones a la misma tienda
    scraping_timeout: int = 30  # Timeout en segundos
    scraping_max_retries: int = 3
    scraping_runtime: str = "http"  # http | browser
    scraping_http_timeout: int = 30
    scraping_http_retries: int = 2
    scraping_http_impersonate: str | None = None
    scraping_http_http3: bool = False
    scraping_http_stealthy_headers: bool = True
    scraping_http_proxy: str | None = None
    scraping_browser_enabled: bool = True
    scraping_browser_headless: bool = True
    scraping_browser_timeout_ms: int = 45000
    scraping_browser_max_pages: int = 3
    scraping_browser_disable_resources: bool = True
    scraping_browser_network_idle: bool = True
    scraping_browser_solve_cloudflare: bool = False
    scraping_browser_real_chrome: bool = False

    # Configuración del scheduler
    scheduler_scrape_interval_hours: int = 6

    # Configuración de OpenLibrary API
    openlibrary_api_url: str = "https://openlibrary.org"
    openlibrary_rate_limit: float = 1.0  # Segundos entre peticiones

    # Configuración de autenticación
    auth_admin_username: str = "admin"
    auth_admin_password: str = "changeme"
    jwt_secret_key: str = "change-me-in-production-32-bytes"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 7


settings = Settings()
