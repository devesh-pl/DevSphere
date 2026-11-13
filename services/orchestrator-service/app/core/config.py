from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "orchestrator-service"
    app_version: str = "0.1.0"
    log_level: str = "INFO"

    database_url: str
    auth_service_url: str = "http://auth-service:8000"

    rabbitmq_host: str = "rabbitmq"
    rabbitmq_port: int = 5672
    rabbitmq_user: str
    rabbitmq_password: str

    operation_queue: str = "devsphere.operations.v1"

    model_config = SettingsConfigDict(extra="ignore")


settings = Settings()
