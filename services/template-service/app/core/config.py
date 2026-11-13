from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "template-service"
    app_version: str = "0.1.0"
    log_level: str = "INFO"
    auth_service_url: str = "http://auth-service:8000"
    template_root: Path = Path("/app/templates/starters")

    model_config = SettingsConfigDict(extra="ignore")


settings = Settings()
