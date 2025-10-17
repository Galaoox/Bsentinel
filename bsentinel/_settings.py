from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="secrets/.env")

    app_name: str = "api-bsentinel"
    app_version: str = "0.1.0"
    app_environment: str = "local"
    port: int = 3030
    log_level: str = "INFO"
    clevertap_account_id: str
    clevertap_passcode: str
    url_api_clevertap: str


settings = Settings()
