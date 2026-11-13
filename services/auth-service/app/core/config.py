from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore",
    )

    service_name: str = "auth-service"

    app_version: str = "0.1.0"

    log_level: str = "INFO"

    database_url: str | None = None

    database_required: bool = True


settings = Settings()