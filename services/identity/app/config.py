from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://baymeister:baymeister@localhost:5432/identity"

    # Порожньо — події пишуться в лог. Так блок піднімається без RabbitMQ.
    rabbitmq_url: str | None = None
    events_exchange: str = "baymeister"

    # PEM прямо в змінній або шлях до файла. Обидва порожні — тимчасовий ключ.
    jwt_private_key: str | None = None
    jwt_private_key_file: str | None = None
    jwt_issuer: str = "baymeister-identity"
    access_token_ttl_seconds: int = 8 * 60 * 60

    bootstrap_owner_email: str | None = None
    bootstrap_owner_password: str | None = None
    bootstrap_owner_name: str = "Власник"

    port: int = 8002
    debug: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
