from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "catalog-service"
    app_version: str = "0.1.0"
    log_level: str = "INFO"
    database_url: str
    auth_service_url: str = "http://auth-service:8000"

    model_config = SettingsConfigDict(
        env_file=None,
        extra="ignore",
    )


settings = Settings()
